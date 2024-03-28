from src.breedgraph.config import SITE_NAME
from src.breedgraph.domain.model.accounts import UserBase, TeamBase
from src.breedgraph.config import PROTOCOL, HOST_ADDRESS, HOST_PORT
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
        if HOST_PORT != 80:
            verify_url = f'{PROTOCOL}://{HOST_ADDRESS}:{HOST_PORT}/verify'
        else:
            verify_url = f'{PROTOCOL}://{HOST_ADDRESS}/verify'
        self.message.set_content(
            f'Hi {user.fullname}. '
            f'Please visit the following link to verify your email address:'
            f'{verify_url + "?token=" + token}'
        )


class AffiliationConfirmedMessage(Email):

    def __init__(self, user: UserBase, team: TeamBase):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} affiliation confirmed'
        self.message.set_content(
            f'Hi {user.fullname}. '
            f'Your affiliation with {team.fullname} has been confirmed. '
            'You can now access data submitted by users that registered with this key.'
        )


class AdminGrantedMessage(Email):

    def __init__(self, user: UserBase, team: TeamBase):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} admin granted'
        self.message.set_content(
            f'Hi {user.fullname}. '
            f'Your administrator status for {team.fullname} has been confirmed. '
            'You can now control access to data submitted by users that registered with this key. '
            'You can also allow new users to register by adding their email address to those allowed. '
        )
