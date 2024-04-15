import json

from email.mime.text import MIMEText

from src.breedgraph.config import SITE_NAME
from src.breedgraph.domain.model.accounts import UserBase, TeamBase
from src.breedgraph.config import get_base_url
from email.message import EmailMessage


class Email:

    def __init__(self):
        self.message = EmailMessage()


class EmailAddedMessage(Email):

    def __init__(self, ):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} registration now available'
        self.message.set_content(
            f'Welcome to {SITE_NAME}. \n'
            f'You are now able to register with this email address.'
        )

class VerifyEmailMessage(Email):

    def __init__(self, user: UserBase, token: str):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} account email verification'
        # options here are a url to a rest endpoint or handle the token posted over graphql
        # this can be done through a form submission disguised as a link but this wouldn't work without html
        # for ease of use for users without html email we have a rest endpoint just for this url
        verify_url = f'{get_base_url()}/verify'
        body = (
            f'Hi {user.fullname}, \n'
            f'Please visit the following link to verify your email address: \n'
            f'{verify_url + "?token=" + token}'
        )
        self.message.set_content(body)
        self.message.add_attachment(
            json.dumps({"token": token, "token2": token, "token3": token}).encode('utf-8'),
            maintype='application',
            subtype='json',
            filename='verify_email_token.json'
        )


class ReadRequestedMessage(Email):

    def __init__(self, requesting_user: UserBase, team: TeamBase):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} read access requested'
        body = (
            f'To all admins for {team.fullname},\n'
            f'{requesting_user.fullname} has requested read access to data written by this team.\n'
            f'Please consider authorising this request.'
        )
        self.message.set_content(body)


#class AffiliationConfirmedMessage(Email):
#
#    def __init__(self, user: UserBase, team: TeamBase):
#        super().__init__()
#        self.message['SUBJECT'] = f'{SITE_NAME} affiliation confirmed'
#        self.message.set_content(
#            f'Hi {user.fullname}. '
#            f'Your affiliation with {team.fullname} has been confirmed. '
#            'You can now access data submitted by users that registered with this key.'
#        )
#
#class AdminGrantedMessage(Email):
#
#    def __init__(self, user: UserBase, team: TeamBase):
#        super().__init__()
#        self.message['SUBJECT'] = f'{SITE_NAME} admin granted'
#        self.message.set_content(
#            f'Hi {user.fullname}. '
#            f'Your administrator status for {team.fullname} has been confirmed. '
#            'You can now control access to data submitted by users that registered with this key. '
#            'You can also allow new users to register by adding their email address to those allowed. '
#        )
