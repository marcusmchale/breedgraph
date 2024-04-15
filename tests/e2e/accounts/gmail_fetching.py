import poplib
import base64
import json

from src.breedgraph.config import MAIL_HOST, MAIL_USERNAME, MAIL_PASSWORD


async def confirm_email_delivered_to_gmail(mailto: str):
    mail_client = poplib.POP3_SSL(f"pop.{MAIL_HOST}", 995)
    mail_client.user(MAIL_USERNAME)
    mail_client.pass_(MAIL_PASSWORD)
    numMessages = len(mail_client.list()[1])
    for i in range(numMessages):
        msg_lines = mail_client.retr(i + 1)[1]
        if mailto in msg_lines[0].decode('utf8'):
            mail_client.quit()
            return True



async def get_json_from_gmail(mailto: str):
    # POP3_MAIL_PORT = 995
    mail_client = poplib.POP3_SSL(f"pop.{MAIL_HOST}", 995)
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
        mail_client.quit()
        return json_content

