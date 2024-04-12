import pytest
import pytest_asyncio
import poplib
import base64
import json

from email import parser

from src.breedgraph import bootstrap
from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.notifications import notifications
from src.breedgraph.config import (
    POP3_MAIL_SERVER,
    POP3_MAIL_PORT,
    MAIL_USERNAME,
    MAIL_PASSWORD
)

@pytest_asyncio.fixture
def bus():
    bus = bootstrap.bootstrap(
        uow=unit_of_work.Neo4jUnitOfWork(),
        notifications=notifications.EmailNotifications()
    )
    yield bus

async def get_json_from_gmail(mailto: str):
    mail_client = poplib.POP3_SSL(POP3_MAIL_SERVER, POP3_MAIL_PORT)
    mail_client.user(MAIL_USERNAME)
    mail_client.pass_(MAIL_PASSWORD)
    numMessages = len(mail_client.list()[1])
    for i in range(numMessages):
        msg_lines = mail_client.retr(i + 1)[1]

        if not mailto in msg_lines[0].decode('utf8'):
            continue

        if not b'Content-Type: application/json' in msg_lines:
            continue

        content_start = msg_lines.index(b'Content-Type: application/json') + 5
        content_lines = [base64.b64decode(i).decode('utf8') for i in msg_lines[content_start: len(msg_lines) -2]]
        json_content = json.loads("".join(content_lines))
        yield json_content

@pytest.mark.asyncio(scope="session")
async def test_get_email(user_input_generator):
    first_user_input = user_input_generator.user_inputs[0]
    async for json_content in get_json_from_gmail(mailto=first_user_input['email']):
        json_content
        import pdb; pdb.set_trace()
        pass
