import pytest_asyncio

from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationRepository

from src.breedgraph.domain.model.accounts import AccountStored, Affiliation, Access, Authorisation

from tests.integration.test_accounts_repository import create_account_input
from tests.integration.test_organisations_repository import create_team_input

@pytest_asyncio.fixture(scope="session")
async def stored_account_with_affiliations(user_input_generator, neo4j_tx) -> AccountStored:
    account_input = await create_account_input(user_input_generator)
    accounts_repo = Neo4jAccountRepository(neo4j_tx)
    stored_account: AccountStored = await accounts_repo.create(account_input)

    team_input = await create_team_input(user_input_generator)
    organisations_repo = Neo4jOrganisationRepository(neo4j_tx)
    organisation = await organisations_repo.create(team_input)

    affiliation_write = Affiliation(
        access=Access.WRITE,
        authorisation=Authorisation.AUTHORISED,
        team=organisation.root.id,
        heritable=False
    )
    affiliation_read = Affiliation(
        access=Access.READ,
        authorisation=Authorisation.AUTHORISED,
        team=organisation.root.id,
        heritable=False
    )
    stored_account.affiliations.append(affiliation_write)
    stored_account.affiliations.append(affiliation_read)

    await accounts_repo.update_seen()
    return stored_account

@pytest_asyncio.fixture(scope="session")
async def stored_account_without_affiliations(user_input_generator, neo4j_tx) -> AccountStored:
    account_input = await create_account_input(user_input_generator)
    accounts_repo = Neo4jAccountRepository(neo4j_tx)
    stored_account: AccountStored = await accounts_repo.create(account_input)
    return stored_account
