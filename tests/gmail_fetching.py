"""
this module isn't used currently as I replaced it with mailhog
but is mostly functional so keeping in case we want to resume testing with gmail,
might want to merge in the updates made to the mailhog_fetching module
"""

import pytest_asyncio
import logging

import poplib
import asyncio

import base64
import json
from email import message_from_bytes, header

from src.breedgraph.config import MAIL_HOST, MAIL_USERNAME, MAIL_PASSWORD
from src.breedgraph.custom_exceptions import TooManyRetries

logger = logging.getLogger(__name__)

async def get_gmail_client():
    gmail_client = poplib.POP3_SSL(f"pop.{MAIL_HOST}", 995)
    gmail_client.user(MAIL_USERNAME)
    gmail_client.pass_(MAIL_PASSWORD)
    return gmail_client

def retry(attempts):
    def func_wrapper(f):
        async def wrapper(*args, **kwargs):
            for attempt in range(attempts):
                result = await f(*args, **kwargs)
                if result is not None:
                    return result
                else:
                    await asyncio.sleep(1)
            raise TooManyRetries
        return wrapper
    return func_wrapper

def decode_mime_words(s):
    s = s.replace('\n', '')  # for some reason header decoding drops whitespace after newlines
    decoded = header.decode_header(s)
    return ''.join(
        [word.decode(encoding or 'utf8') if isinstance(word, bytes) else word for word, encoding in decoded]
    )


@retry(30)
async def confirm_email_delivered_to_gmail(mailto: str, subject: str):
    gmail_client = await get_gmail_client()
    num_messages = len(gmail_client.list()[1])
    if "read access for" in subject:
        import pdb; pdb.set_trace()
    for i in range(num_messages):
        msg_lines = gmail_client.retr(i + 1)[1]
        message_bytes = b'\n'.join(msg_lines)
        message = message_from_bytes(message_bytes)
        if mailto in message['Bcc'] and decode_mime_words(message['subject']) == subject:
            gmail_client.quit()
            return True

@retry(30)
async def get_json_from_gmail(mailto: str, subject: str):
    gmail_client = await get_gmail_client()
    num_messages = len(gmail_client.list()[1])
    for i in range(num_messages):
        msg_lines = gmail_client.retr(i + 1)[1]
        message_bytes = b'\n'.join(msg_lines)
        message = message_from_bytes(message_bytes)
        if mailto in message['Bcc'] and decode_mime_words(message['subject']) == subject:
            for j in message.get_payload():
                if j['Content-Type'] == 'application/json':
                    gmail_client.quit()
                    return json.loads(base64.b64decode(j.get_payload()))

