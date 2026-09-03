from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.service_layer.messagebus import MessageBus

from breedgraph.domain.model.accounts import AccountInput, UserInput, OntologyRole, AccountStored
from breedgraph.domain.model.organisations import Organisation, TeamInput, Affiliation, Authorisation
from breedgraph.domain.model.controls import Access

from breedcafs_migration.setup.config import BREEDCAFS_USER_NAME

import logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def create_breedcafs_migration_account(uow_factory: Neo4jUnitOfWorkFactory) -> AccountStored:
    async with uow_factory.get_uow() as uow:
        logger.info("Creating BreedCAFS migration account...")
        migration_account = await uow.repositories.accounts.create(
            AccountInput(
                user=UserInput(
                    name=BREEDCAFS_USER_NAME,
                    fullname=BREEDCAFS_USER_NAME,
                    email='',
                    password_hash='',
                    ontology_role=OntologyRole.ADMIN
                )
            )
        )
        await uow.commit()
        return migration_account

async def create_breedcafs_migration_organisation(user_id: int, uow_factory: Neo4jUnitOfWorkFactory) -> None:
    async with uow_factory.get_uow(user_id=user_id) as uow:
        logger.info("Creating BreedCAFS migration organisation...")
        migration_organisation = await uow.repositories.organisations.create(
            TeamInput(
                name="BreedCAFS",
            )
        )
        migration_team = migration_organisation.add_team(TeamInput(name="Migration"), parent_id=migration_organisation.root.id)
        migration_team.affiliations.set_by_access(Access.READ, user_id, Affiliation(authorisation=Authorisation.AUTHORISED, heritable=False))
        migration_team.affiliations.set_by_access(Access.WRITE, user_id, Affiliation(authorisation=Authorisation.AUTHORISED, heritable=False))
        await uow.commit()

async def setup_breedcafs_migration_account(uow_factory: Neo4jUnitOfWorkFactory) -> int:
    migration_account = await create_breedcafs_migration_account(uow_factory=uow_factory)
    await create_breedcafs_migration_organisation(user_id=migration_account.user.id, uow_factory=uow_factory)
    return migration_account.user.id


