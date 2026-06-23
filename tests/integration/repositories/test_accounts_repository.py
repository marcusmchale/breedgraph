import pytest

from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory
from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.custom_exceptions import NoResultFoundError

from tests.scenarios.account_builder import AccountBuilder

@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get_account(uow_factory: AbstractUnitOfWorkFactory):
    account_input = AccountBuilder.account_input()
    async with uow_factory.get_uow() as uow:
        accounts_repo = uow.repositories.accounts
        stored_account: AccountStored = await accounts_repo.create(account_input)
        await uow.commit()

    async with uow_factory.get_uow() as uow:
        accounts_repo = uow.repositories.accounts
        account_by_id = await accounts_repo.get(user_id=stored_account.user.id)
        assert account_by_id.user.name == account_input.user.name
        account_by_name = await accounts_repo.get(name=stored_account.user.name)
        assert account_by_name.user.id == stored_account.user.id
        account_by_email = await accounts_repo.get(email=account_input.user.email)
        assert account_by_email.user.name == account_input.user.name

    async with uow_factory.get_uow() as uow:
        accounts_repo = uow.repositories.accounts
        async for account in accounts_repo.get_all():
            if account.user.name == account_input.user.name:
                break
        else:
            raise NoResultFoundError("Created account is not retrieved by get_all")

@pytest.mark.asyncio(loop_scope="session")
async def test_change_user_details_on_account(uow_factory):
    account_input = AccountBuilder.account_input()

    async with uow_factory.get_uow() as uow:
        accounts_repo = uow.repositories.accounts
        stored_account: AccountStored = await accounts_repo.create(account_input)

        changed_account_input = AccountBuilder.account_input()
        assert changed_account_input.user.name != account_input.user.name

        stored_account.user.name = changed_account_input.user.name
        stored_account.user.email = changed_account_input.user.email
        stored_account.user.fullname = changed_account_input.user.name
        await uow.commit()

    async with uow_factory.get_uow() as uow:
        accounts_repo = uow.repositories.accounts
        retrieved_stored_account = await accounts_repo.get(user_id=stored_account.user.id)
        assert retrieved_stored_account.user.name == changed_account_input.user.name