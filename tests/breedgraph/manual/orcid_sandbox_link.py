#!/usr/bin/env python3
"""
Links an ORCID iD to the user's Person on a running BreedGraph server, without the front end.
For testing against the ORCID sandbox until the front-end /orcid page exists.

Load the env files and start the server, then run with the same env files loaded:
    python scripts/orcid_sandbox_link.py --username <user>   # link
    python scripts/orcid_sandbox_link.py --create-user       # create a test user first, after the tests wipe the database
    python scripts/orcid_sandbox_link.py --remove            # remove the iD again

The user must be linked to a Person (peopleMyPerson). --create-user writes to the configured Neo4j database directly,
creating a verified user with a random password, a team and a linked Person, and prints the login. The script opens ORCID's sign-in URL in a browser.
If ORCID_REDIRECT_URI is an http://localhost or http://127.0.0.1 URI and its port is free (stop the front-end dev server),
the script listens there and catches the redirect itself. Otherwise paste the URL ORCID redirected to
(the page itself need not load), or just its code and state.
The state expires after ORCID_STATE_EXPIRES_SECONDS.
"""
import argparse
import asyncio
import getpass
import secrets
import socket
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import bcrypt
import requests

from breedgraph.config import get_base_url, GQL_API_PATH, ORCID_BASE_URL, ORCID_REDIRECT_URI
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.domain.model import Access
from breedgraph.domain.model.accounts import AccountInput, UserInput
from breedgraph.domain.model.organisations import TeamInput, Affiliation, Authorisation
from breedgraph.domain.model.people import PersonInput

BASE_URL = get_base_url()


class Client:
    def __init__(self):
        resp = requests.post(f"{BASE_URL}csrf", timeout=10)
        resp.raise_for_status()
        self.csrf_token = resp.json()['token']
        self.auth_token = None

    def gql(self, query: str, variables: dict | None = None) -> dict:
        cookie = f"csrf_token={self.csrf_token}"
        if self.auth_token:
            cookie += f"; auth_token={self.auth_token}"
        resp = requests.post(
            f"{BASE_URL}{GQL_API_PATH}",
            json={'query': query, 'variables': variables or {}},
            headers={'X-CSRF-Token': self.csrf_token, 'Cookie': cookie},
            timeout=30
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get('errors'):
            raise SystemExit(f"GraphQL errors: {body['errors']}")
        payload = next(iter(body['data'].values()))
        if payload.get('errors'):
            raise SystemExit(f"Failed: {payload['errors']}")
        # The auth cookie is Secure, so set it by hand rather than relying on a cookie jar over http
        if 'auth_token' in resp.cookies:
            self.auth_token = resp.cookies['auth_token']
        return payload


def code_and_state(params: dict) -> tuple[str, str]:
    if 'error' in params:
        raise SystemExit(f"ORCID returned an error: {params['error'][0]} {params.get('error_description', [''])[0]}")
    try:
        return params['code'][0], params['state'][0]
    except KeyError:
        raise SystemExit("The URL has no code and state")


def read_code_and_state() -> tuple[str, str]:
    entered = input("Paste the redirected URL (or press enter to type the code and state): ").strip()
    if not entered:
        return input("code: ").strip(), input("state: ").strip()
    return code_and_state(parse_qs(urlparse(entered).query))


class DualStackServer(HTTPServer):
    # Browsers may resolve localhost to ::1 or 127.0.0.1, so accept both
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def redirect_listener() -> HTTPServer | None:
    """A server on the redirect URI's port, if it is a free local http port"""
    redirect = urlparse(ORCID_REDIRECT_URI)
    if redirect.scheme != 'http' or redirect.hostname not in ('localhost', '127.0.0.1'):
        return None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path.rstrip('/') != redirect.path.rstrip('/'):
                self.send_error(404)
                return
            self.server.params = parse_qs(url.query)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"Received the ORCID response, you can close this tab and return to the terminal.")

        def log_message(self, *args):
            pass

    port = redirect.port or 80
    try:
        server = DualStackServer(('::', port), Handler)
    except OSError:
        try:
            server = HTTPServer(('127.0.0.1', port), Handler)
        except OSError as e:
            print(f"Cannot listen on port {port} ({e.strerror}), so paste the redirected URL instead")
            return None
    server.params = None
    return server


def await_redirect(server: HTTPServer) -> tuple[str, str]:
    print(f"Waiting for ORCID to redirect to {ORCID_REDIRECT_URI} (ctrl+c to stop)")
    try:
        while server.params is None:
            server.handle_request()
    finally:
        server.server_close()
    return code_and_state(server.params)


async def create_test_user() -> tuple[str, str]:
    """A verified user, with full access to a new team, linked to a Person that team controls"""
    name = f"orcid-sandbox-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(12)
    driver = Neo4jAsyncDriver()
    try:
        uow_factory = Neo4jUnitOfWorkFactory(driver)
        async with uow_factory.get_uow() as uow:
            account = await uow.repositories.accounts.create(AccountInput(user=UserInput(
                name=name,
                fullname="ORCID Sandbox Tester",
                email=f"{name}@example.org",
                email_verified=True,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            )))
            await uow.commit()
        user_id = account.user.id
        async with uow_factory.get_uow(user_id=user_id) as uow:
            organisation = await uow.repositories.organisations.create(TeamInput(name=f"{name} team"))
            await uow.commit()
        team_id = organisation.root.id
        async with uow_factory.get_uow(user_id=user_id, redacted=False) as uow:
            team = (await uow.repositories.organisations.get(team_id=team_id)).get_team(team_id)
            for access in Access:
                team.affiliations.set_by_access(access, user_id, Affiliation(authorisation=Authorisation.AUTHORISED, heritable=False))
            await uow.commit()
        async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
            person = await uow.repositories.people.create(
                PersonInput(name="ORCID Sandbox Tester", teams=[team_id], informed_attestation=True)
            )
            await uow.commit()
        async with uow_factory.get_uow(user_id=user_id) as uow:
            person = await uow.repositories.people.get(person_id=person.id)
            person.link(user_id)
            await uow.commit()
    finally:
        await driver.close()
    print(f"Created BreedGraph user {name} with password {password}, linked to Person {person.id}")
    return name, password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--remove', action='store_true', help="remove the ORCID iD instead of linking one")
    parser.add_argument('--username', help="the BreedGraph user to link the ORCID iD to")
    parser.add_argument('--create-user', action='store_true', help="create a test user linked to a Person, and use it")
    parser.add_argument('--no-listen', action='store_true', help="paste the redirected URL instead of listening for it")
    args = parser.parse_args()

    print(f"Server: {BASE_URL}\nORCID: {ORCID_BASE_URL}\nRedirect URI: {ORCID_REDIRECT_URI}")
    client = Client()
    if args.create_user:
        username, password = asyncio.run(create_test_user())
    else:
        username = args.username or input("BreedGraph username: ")
        password = getpass.getpass("BreedGraph password: ")
    client.gql(
        "mutation ($username: String!, $password: String!) { accountsLogin(username: $username, password: $password) "
        "{ status, result, errors { name, message } } }",
        {'username': username, 'password': password}
    )
    if not client.auth_token:
        raise SystemExit("Login did not return an auth_token cookie")

    my_person = "query { peopleMyPerson { status, result { id, name, orcid }, errors { name, message } } }"
    person = client.gql(my_person)['result']
    print(f"Person {person['id']} ({person['name']}), current ORCID iD: {person['orcid']}")

    if args.remove:
        client.gql("mutation { peopleRemoveOrcid { status, result, errors { name, message } } }")
    else:
        url = client.gql("mutation { peopleStartOrcidLink { status, result, errors { name, message } } }")['result']
        # Listen before opening the browser, so the redirect cannot arrive first
        server = None if args.no_listen else redirect_listener()
        print(f"\nSign in with your ORCID account at:\n\n{url}\n")
        webbrowser.open(url)
        code, state = await_redirect(server) if server else read_code_and_state()
        client.gql(
            "mutation ($code: String!, $state: String!) { peopleCompleteOrcidLink(code: $code, state: $state) "
            "{ status, result, errors { name, message } } }",
            {'code': code, 'state': state}
        )

    person = client.gql(my_person)['result']
    print(f"Done. ORCID iD is now: {person['orcid']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
