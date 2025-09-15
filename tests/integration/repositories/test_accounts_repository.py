import pytest

from src.breedgraph.domain.model.accounts import UserInput, AccountInput, AccountStored
from src.breedgraph.adapters.neo4j import Neo4jAccountRepository
from src.breedgraph.custom_exceptions import NoResultFoundError

async def create_account_input(user_input_generator) -> AccountInput:
    new_user_input = user_input_generator.new_user_input()
    new_user = UserInput(
        name=new_user_input['name'],
        fullname=new_user_input['name'],
        email=new_user_input['email'],
        password_hash=new_user_input['password_hash']
    )
    return AccountInput(user=new_user)

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_and_get_account(uncommitted_neo4j_tx, user_input_generator):
    account_input = await create_account_input(user_input_generator)
    accounts_repo = Neo4jAccountRepository(uncommitted_neo4j_tx)
    stored_account: AccountStored = await accounts_repo.create(account_input)
    assert stored_account.user.name == account_input.user.name

    retrieved_account = await accounts_repo.get(user_id=stored_account.user.id)
    assert retrieved_account.user.name == account_input.user.name

    retrieved_account = await accounts_repo.get(name=stored_account.user.name)
    assert retrieved_account.user.name == account_input.user.name

    retrieved_account = await accounts_repo.get(email=account_input.user.email)
    assert retrieved_account.user.name == account_input.user.name

    async for account in accounts_repo.get_all():
        if account.user.name == account_input.user.name:
            break
    else:
        raise NoResultFoundError("Account is not retrieved by get_all without filters")

@pytest.mark.asyncio(scope="session")
async def test_change_user_details_on_account(uncommitted_neo4j_tx, user_input_generator):
    new_account_input = await create_account_input(user_input_generator)
    accounts_repo = Neo4jAccountRepository(uncommitted_neo4j_tx)
    stored_account: AccountStored = await accounts_repo.create(new_account_input)

    changed_account_input = await create_account_input(user_input_generator)
    stored_account.user.name = changed_account_input.user.name
    stored_account.user.email = changed_account_input.user.email
    stored_account.user.fullname = changed_account_input.user.name

    await accounts_repo.update_seen()

    retrieved_stored_account = await accounts_repo.get(user_id=stored_account.user.id)
    assert retrieved_stored_account.user == stored_account.user