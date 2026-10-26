#!/usr/bin/env python3
"""
Creates the site's first account, once, on the server (docs/deployment.md). Registering in BreedView needs an
invitation, which only an account can send, so the first is made here, by whoever runs the server, and nobody can
register before them. It is verified, and the first ontology admin, who can make others editors and admins.

From a checkout of the release, with the API's venv and environment loaded, after scripts/setup_initial_data.py:

    python scripts/create_first_account.py --name <username> --email <address> [--fullname "<full name>"]

It asks for the password twice, held to the site's password policy, and for the account holder's consent to the
privacy notice the site serves, which it records as registering does. It refuses once any verified account exists,
and prints the new account's id.
"""
import argparse
import asyncio
import getpass
import sys
from datetime import datetime, timezone

import bcrypt

from breedgraph import config
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.accounts import AccountInput, UserInput, OntologyRole
from breedgraph.service_layer.application.terms_of_use import load_legal_text


class Refused(Exception):
    pass


async def create_first_account(
        uow_factory, name: str, email: str, password_hash: str, privacy_notice_hash: str, fullname: str | None = None
) -> int:
    """The site's first account, verified and the first ontology admin; refused once a verified account exists"""
    async with uow_factory.get_uow() as uow:
        if await uow.constraints.accounts_exist():
            raise Refused("The site has an account already: invite others from BreedView instead")
        for found in (await uow.repositories.accounts.get(name=name), await uow.repositories.accounts.get(email=email)):
            if found is not None:
                raise Refused("An unverified account has this username or email address: choose another")
        account = await uow.repositories.accounts.create(AccountInput(user=UserInput(
            name=name,
            fullname=fullname or name,
            email=email,
            password_hash=password_hash,
            ontology_role=OntologyRole.ADMIN,
            privacy_consented_at=datetime.now(timezone.utc),
            privacy_notice_hash=privacy_notice_hash
        )))
        account.verify_email()
        await uow.commit()
        return account.user.id


async def run(name: str, email: str, password_hash: str, privacy_notice_hash: str, fullname: str | None) -> int:
    driver = Neo4jAsyncDriver()
    try:
        return await create_first_account(
            Neo4jUnitOfWorkFactory(driver), name, email, password_hash, privacy_notice_hash, fullname
        )
    finally:
        await driver.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the site's first account, once")
    parser.add_argument('--name', required=True, help='the username')
    parser.add_argument('--email', required=True)
    parser.add_argument('--fullname', help='shown to other users; the username by default')
    args = parser.parse_args()
    if '@' not in args.email:
        print(f"Not an email address: {args.email}", file=sys.stderr)
        return 1

    notice = load_legal_text(config.PRIVACY_NOTICE_PATH)
    print(f"The privacy notice the site serves is {config.PRIVACY_NOTICE_PATH}, which BreedView shows too.")
    if input("Do you consent to the processing of your personal data as it describes? [yes/no] ").strip().lower() != 'yes':
        print("An account needs that consent, as registering does", file=sys.stderr)
        return 1

    password = getpass.getpass("Password: ")
    errors = config.get_password_policy().test(password)
    if errors:
        print(f"The password does not meet the policy: {', '.join(str(e) for e in errors)}", file=sys.stderr)
        return 1
    if getpass.getpass("Password again: ") != password:
        print("The passwords differ", file=sys.stderr)
        return 1

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        user_id = asyncio.run(run(args.name, args.email, password_hash, notice.content_hash, args.fullname))
    except Refused as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Created account {user_id}, {args.name}, the first ontology admin: sign in to BreedView with it")
    return 0


if __name__ == '__main__':
    sys.exit(main())
