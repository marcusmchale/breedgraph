"""
Set up the identity the migration runs as (README.md, Migration Bootstrap):
a BreedCAFS Migration user, affiliated with a BreedCAFS Migration team
under an existing team of an organisation that has declared a legal entity (University of Galway).

The migration user is a system account. It has no email or password, so it cannot log in,
and it is created directly rather than through CreateAccount, which requires an invitation.
The team and affiliations are created by an admin of the parent team, through the Organisation aggregate.

Every step finds what an earlier run created, so the bootstrap can be run again.
"""
from dataclasses import dataclass

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory

from breedgraph.domain.model.accounts import AccountInput, UserInput, OntologyRole, AccountStored
from breedgraph.domain.model.organisations import Organisation, TeamInput, TeamStored
from breedgraph.domain.model.controls import Access

from breedcafs_migration.setup.config import (
    BREEDCAFS_USER_NAME, BREEDCAFS_TEAM_NAME, BREEDCAFS_ADMIN_USER_ID, BREEDCAFS_PARENT_TEAM_ID
)

import logging
logger = logging.getLogger(__name__)

# CURATE also authorises READ
MIGRATION_ACCESS = [Access.WRITE, Access.CURATE]


@dataclass(frozen=True)
class MigrationContext:
    user_id: int
    team_id: int


async def get_or_create_migration_account(uow_factory: Neo4jUnitOfWorkFactory) -> AccountStored:
    async with uow_factory.get_uow(redacted=False) as uow:
        account = await uow.repositories.accounts.get(name=BREEDCAFS_USER_NAME)
        if account is not None:
            if account.user.password_hash:
                raise ValueError(f"An account named {BREEDCAFS_USER_NAME} exists and is not the migration system account")
            logger.info("Using the existing BreedCAFS migration account")
            return account

        logger.info("Creating the BreedCAFS migration account")
        account = await uow.repositories.accounts.create(
            AccountInput(
                user=UserInput(
                    name=BREEDCAFS_USER_NAME,
                    fullname=BREEDCAFS_USER_NAME,
                    ontology_role=OntologyRole.EDITOR
                )
            )
        )
        await uow.commit()
        return account


def get_child_team(organisation: Organisation, parent_id: int, name: str) -> TeamStored | None:
    for team in organisation.get_sinks(parent_id).values():
        if team.name.casefold() == name.casefold():
            return team
    return None


async def get_or_create_migration_team(uow_factory: Neo4jUnitOfWorkFactory, admin_id: int, parent_id: int) -> int:
    async with uow_factory.get_uow(user_id=admin_id) as uow:
        organisation: Organisation = await uow.repositories.organisations.get(team_id=parent_id)
        if organisation is None:
            raise ValueError(f"Parent team {parent_id} not found")
        if organisation.legal_entity is None:
            raise ValueError("The parent team's organisation has not declared a legal entity, which Persons require")
        if admin_id not in organisation.get_affiliates(parent_id, Access.ADMIN):
            raise ValueError(f"User {admin_id} is not an admin of the parent team {parent_id}")

        team = get_child_team(organisation, parent_id, BREEDCAFS_TEAM_NAME)
        if team is not None:
            logger.info("Using the existing BreedCAFS migration team")
            return team.id

        logger.info("Creating the BreedCAFS migration team")
        organisation.add_team(TeamInput(name=BREEDCAFS_TEAM_NAME, fullname=BREEDCAFS_TEAM_NAME), parent_id=parent_id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=admin_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=parent_id)
        return get_child_team(organisation, parent_id, BREEDCAFS_TEAM_NAME).id


async def affiliate_migration_user(uow_factory: Neo4jUnitOfWorkFactory, admin_id: int, user_id: int, team_id: int) -> None:
    async with uow_factory.get_uow(user_id=admin_id) as uow:
        organisation: Organisation = await uow.repositories.organisations.get(team_id=team_id)
        if admin_id not in organisation.get_affiliates(team_id, Access.ADMIN):
            raise ValueError(f"User {admin_id} is not an admin of the migration team; admin of the parent team must be heritable")

        for access in MIGRATION_ACCESS:
            if user_id in organisation.get_affiliates(team_id, access, inheritance=False):
                continue
            logger.info(f"Affiliating the migration user with {access.name} access")
            organisation.request_affiliation(agent_id=user_id, user_id=user_id, team_id=team_id, access=access)
            organisation.authorise_affiliation(agent_id=admin_id, user_id=user_id, team_id=team_id, access=access)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        account = await uow.repositories.accounts.get(user_id=user_id)
        if account.user.default_write_team != team_id:
            account.user.default_write_team = team_id
            await uow.commit()


async def setup_breedcafs_migration_account(uow_factory: Neo4jUnitOfWorkFactory) -> MigrationContext:
    if BREEDCAFS_ADMIN_USER_ID is None or BREEDCAFS_PARENT_TEAM_ID is None:
        raise ValueError("Set BREEDCAFS_ADMIN_USER_ID and BREEDCAFS_PARENT_TEAM_ID")
    admin_id = int(BREEDCAFS_ADMIN_USER_ID)
    parent_id = int(BREEDCAFS_PARENT_TEAM_ID)

    account = await get_or_create_migration_account(uow_factory)
    team_id = await get_or_create_migration_team(uow_factory, admin_id=admin_id, parent_id=parent_id)
    await affiliate_migration_user(uow_factory, admin_id=admin_id, user_id=account.user.id, team_id=team_id)
    return MigrationContext(user_id=account.user.id, team_id=team_id)
