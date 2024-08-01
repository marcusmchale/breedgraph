import pytest_asyncio

from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationRepository

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.organisations import Organisation, Affiliation, Access, Authorisation

from tests.integration.test_accounts_repository import create_account_input
from tests.integration.test_organisations_repository import create_team_input

@pytest_asyncio.fixture(scope="session")
async def stored_account(user_input_generator, neo4j_tx) -> AccountStored:
    account_input = await create_account_input(user_input_generator)
    accounts_repo = Neo4jAccountRepository(neo4j_tx)
    stored_account: AccountStored = await accounts_repo.create(account_input)
    await accounts_repo.update_seen()
    return stored_account

@pytest_asyncio.fixture(scope="session")
async def second_account(user_input_generator, neo4j_tx) -> AccountStored:
    account_input = await create_account_input(user_input_generator)
    accounts_repo = Neo4jAccountRepository(neo4j_tx)
    second_account: AccountStored = await accounts_repo.create(account_input)
    await accounts_repo.update_seen()
    return second_account

@pytest_asyncio.fixture(scope="session")
async def stored_organisation(user_input_generator, neo4j_tx, stored_account) -> Organisation:
    team_input = await create_team_input(user_input_generator)
    organisations_repo = Neo4jOrganisationRepository(neo4j_tx, account=stored_account)
    organisation = await organisations_repo.create(team_input)
    await organisations_repo.update_seen()
    return organisation
