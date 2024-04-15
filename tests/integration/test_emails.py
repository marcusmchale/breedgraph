import pytest
import pytest_asyncio
import poplib
import base64
import json
import requests

from src.breedgraph.config import (
    MAIL_HOST,
    MAIL_PORT,
    MAIL_USERNAME,
    MAIL_PASSWORD
)

from src.breedgraph.domain.commands.accounts import (
    AddAccount,
    VerifyEmail
)


async def get_email_from_mailhog(mailto: str):
    all_emails = requests.get(f'http://{MAIL_HOST}:{MAIL_PORT}/api/v2/messages').json()
    import pdb; pdb.set_trace()
    yield next(m for m in all_emails['items'])

#@pytest.mark.usefixtures("session_database")
#@pytest.mark.asyncio(scope="session")
#async def test_add_account_and_verify_email(bus, user_input_generator):
#    user_input = user_input_generator.new_user_input()
#
#    async with bus.uow as uow:
#        first_account = await uow.accounts.get(1)
#        first_account.allowed_emails.append(user_input['email'])
#        await uow.commit()
#
#    add_account = AddAccount(
#        name = user_input['name'],
#        email = user_input['email'],
#        fullname= user_input['name'],
#        password_hash = user_input['password_hash']
#    )
#    await bus.handle(add_account)
#
#    async with bus.uow as uow:
#        account = await uow.accounts.get_by_email(user_input['email'])
#        assert account.user.email_verified == False
#
#    #async for json_content in get_json_from_gmail(mailto=user_input['email']):
#    async for json_content in get_email_from_mailhog(mailto=user_input['email']):
#        pass
#    #    await bus.handle(VerifyEmail(token=json_content['token']))
#
#
#    async with bus.uow as uow:
#        account = await uow.accounts.get_by_email(user_input['email'])
#        assert account.user.email_verified == True