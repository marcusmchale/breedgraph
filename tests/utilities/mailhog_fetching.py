import asyncio
import base64
import json
import requests
import quopri
from email import header

from src.breedgraph.config import MAIL_HOST

from tests.utilities.exceptions import TooManyRetries


MAILHOG_HTTP_PORT = 8025


def replace_linebreaks(s):
    s= s.replace('=\r', '')  # this is a soft-line break see http://www.faqs.org/rfcs/rfc2045.html
    s = s.replace('\n', '')
    s = s.replace('\r', '')
    return s

def decode_mime_words(s):
    s = replace_linebreaks(s)
    decoded = header.decode_header(s)
    return ''.join(
        [word.decode(encoding or 'utf8') if isinstance(word, bytes) else word for word, encoding in decoded]
    )

def decode_quopri(s):
    return replace_linebreaks(quopri.decodestring(s).decode('utf8'))

def decode_b64(b):
    s = base64.b64decode(b).decode('utf8')
    return replace_linebreaks(s)


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


@retry(10)
async def get_email(mailto: str, subject: str, string_in_body: None|str = None):
    all_emails = requests.get(f'http://{MAIL_HOST}:{MAILHOG_HTTP_PORT}/api/v2/messages').json()
    for e in all_emails['items']:
        if all([
            mailto in e['Raw']['To'],
            subject in [decode_mime_words(w) for w in e['Content']['Headers']['SUBJECT']]
        ]):
            if string_in_body is not None:
                #if not string_in_body in decode_mime_words(e['Content']['Body']):
                if not string_in_body in decode_quopri(e['Content']['Body']):
                    try:
                        body = decode_b64(e['Content']['Body'])
                        if not string_in_body in body:
                            continue
                    except UnicodeDecodeError:
                        continue

            return e
    return None

async def confirm_email_delivered(mailto: str, subject: str, string_in_body: None|str = None):
    if await get_email(mailto, subject, string_in_body):
        return True
    else:
        return False

async def get_json_from_email(mailto: str, subject: str, string_in_body: None|str = None):
    e = await get_email(mailto, subject, string_in_body)
    if e:
        for part in e['MIME']['Parts']:
            if 'application/json' in part['Headers']['Content-Type']:
                return json.loads(base64.b64decode(part['Body']))
    return None
