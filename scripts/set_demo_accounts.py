#!/usr/bin/env python3
"""
Set up the accounts of the hosted demonstration site (instance/demo/README.md) on a freshly loaded demonstration
database: give the story's accounts the site's passwords, and add the reviewers' accounts. scripts/reset_demo.sh runs it
after each load; run it by hand after changing the accounts file.

The accounts file is private to the server (mode 0600), a JSON object:

    {
      "accounts": {"dara": "...", "bridget": "...", "theo": "...", "lena": "...", "petra": "..."},
      "reviewers": [
        {"username": "dpo-reviewer-1", "fullname": "DPO reviewer 1", "email": "dpo-reviewer-1@example.org",
         "password": "...", "teams": {"institute": ["READ"]}}
      ]
    }

"accounts" holds a password for each story account (tests/breedgraph/scenarios/demo/story.py ACCOUNTS), but for those
the build deletes (rita), whose writes show an account without a Person record. Each reviewer
is a verified account; "teams", optional, gives it affiliations by story team key (institute, breeding, field, lab,
cooperative), heritable as the team tree's owner grants them, so that READ on the Institute reads its teams' private
records too. Every account is recorded as consenting to the privacy notice the site serves (PRIVACY_NOTICE_PATH), so
that signing in doesn't ask again.

    python scripts/set_demo_accounts.py --accounts /opt/breedgraph-demo/private/demo_accounts.json

It refuses to run unless BREEDGRAPH_DEMO=1, which only the demonstration site's environment sets: it would change the
passwords of any account named like a story account.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import bcrypt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.config import PRIVACY_NOTICE_PATH
from breedgraph.domain.model.accounts import AccountInput, UserInput
from breedgraph.domain.model.controls import Access
from breedgraph.service_layer.application.terms_of_use import load_legal_text

from tests.breedgraph.scenarios.authorisation_manager import AuthorisationManager
from tests.breedgraph.scenarios.demo.story import ACCOUNTS as STORY_ACCOUNTS, TEAMS

# the story's accounts the database has: the build deletes some
ACCOUNTS = {key: account for key, account in STORY_ACCOUNTS.items() if not account.deleted}

import logging
from breedgraph.config.logging import log_to_console
logger = logging.getLogger(__name__)


def hashed(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def read_accounts(path: Path) -> dict:
    """The accounts file, checked: a password for each story account, and each reviewer named, with a password"""
    given = json.loads(path.read_text())
    missing = [key for key in ACCOUNTS if not given.get('accounts', {}).get(key)]
    if missing:
        raise SystemExit(f"{path} has no password for {', '.join(missing)}")
    for reviewer in given.get('reviewers', []):
        for field in ('username', 'fullname', 'email', 'password'):
            if not reviewer.get(field):
                raise SystemExit(f"{path}: a reviewer has no {field}")
        if reviewer['username'] in ACCOUNTS:
            raise SystemExit(f"{path}: the reviewer {reviewer['username']} has a story account's name")
        unknown = [team for team in reviewer.get('teams', {}) if team not in TEAMS]
        if unknown:
            raise SystemExit(f"{path}: {reviewer['username']} names no story team {', '.join(unknown)}")
    return given


def team_owner(team: str) -> str:
    """The story account owning a team's tree, who administers every team in it"""
    while TEAMS[team].parent is not None:
        team = TEAMS[team].parent
    return TEAMS[team].owner


async def team_ids(uow_factory, owner_ids: dict[str, int]) -> dict[str, int]:
    """Each story team's id, by its name, from the team trees its owners see"""
    ids = {}
    for key, team in TEAMS.items():
        if team.parent is not None:
            continue
        async with uow_factory.get_uow(user_id=owner_ids[team.owner]) as uow:
            async for tree in uow.repositories.team_trees.get_all():
                names = {tree.get_team(team_id).name: team_id for team_id in tree.entries}
                for other, other_team in TEAMS.items():
                    if other_team.name in names:
                        ids.setdefault(other, names[other_team.name])
    return ids


async def set_accounts(uow_factory, given: dict, consented_at: datetime, notice_hash: str) -> dict[str, int]:
    """Set the story accounts' passwords and consent, and add or update the reviewers: their ids by username"""
    ids = {}
    for key in ACCOUNTS:
        async with uow_factory.get_uow() as uow:
            account = await uow.repositories.accounts.get(name=key)
            if account is None:
                raise SystemExit(f"The database has no account {key}: is it the demonstration database?")
            account.user.password_hash = hashed(given['accounts'][key])
            account.user.privacy_consented_at = consented_at
            account.user.privacy_notice_hash = notice_hash
            await uow.commit()
            ids[key] = account.user.id
    for reviewer in given.get('reviewers', []):
        async with uow_factory.get_uow() as uow:
            account = await uow.repositories.accounts.get(name=reviewer['username'])
            if account is None:
                account = await uow.repositories.accounts.create(AccountInput(user=UserInput(
                    name=reviewer['username'],
                    fullname=reviewer['fullname'],
                    email=reviewer['email'],
                    password_hash=hashed(reviewer['password']),
                    email_verified=True,
                    privacy_consented_at=consented_at,
                    privacy_notice_hash=notice_hash
                )))
            else:
                account.user.password_hash = hashed(reviewer['password'])
                account.user.privacy_consented_at = consented_at
                account.user.privacy_notice_hash = notice_hash
            await uow.commit()
            ids[reviewer['username']] = account.user.id
    return ids


async def set_affiliations(uow_factory, given: dict, ids: dict[str, int]):
    """Each reviewer's affiliations, granted by the owner of the team's tree, heritable but for Write"""
    teams = await team_ids(uow_factory, ids)
    authorisations = AuthorisationManager(uow_factory)
    for reviewer in given.get('reviewers', []):
        for team, accesses in reviewer.get('teams', {}).items():
            for access in accesses:
                await authorisations.authorise_affiliation(
                    agent_id=ids[team_owner(team)], user_id=ids[reviewer['username']], team_id=teams[team],
                    access=Access[access], heritable=access != 'WRITE'
                )


async def main(accounts_path: Path):
    given = read_accounts(accounts_path)
    # no message bus, as for the build (scripts/database_builds.py): account events would send email
    driver = Neo4jAsyncDriver()
    try:
        uow_factory = Neo4jUnitOfWorkFactory(driver)
        notice_hash = load_legal_text(PRIVACY_NOTICE_PATH).content_hash
        ids = await set_accounts(uow_factory, given, datetime.now(timezone.utc), notice_hash)
        await set_affiliations(uow_factory, given, ids)
        logger.info("Set %s story accounts and %s reviewers", len(ACCOUNTS), len(given.get('reviewers', [])))
    finally:
        await driver.close()


if __name__ == '__main__':
    log_to_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--accounts', type=Path, required=True, help="the private JSON file of the site's accounts")
    args = parser.parse_args()
    if os.environ.get('BREEDGRAPH_DEMO') != '1':
        raise SystemExit("Refused: BREEDGRAPH_DEMO=1 is not set, as it is only in the demonstration site's environment")
    asyncio.run(main(args.accounts))
