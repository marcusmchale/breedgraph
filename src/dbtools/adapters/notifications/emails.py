from src.dbtools.config import SITE_NAME
from src.dbtools.domain.model.accounts import UserRegistered, Team
from src.dbtools.config import HOST_ADDRESS
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


class UserConfirmMessage(Email):

    def __init__(self, user: UserRegistered, token: str):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} account confirmation'
        # options here are a url to a rest endpoint or handle the token posted over graphql
        # this can be done through a form submission disguised as a link but this wouldn't work without html
        # for ease of use for users without html email we have a rest endpoint just for this url

        confirm_url = f'https://{HOST_ADDRESS}/confirm'
        self.message.set_content(
            f'Hi {user.fullname}. '
            f'Please visit the following link to confirm your registration: {confirm_url + "?" + token}'
        )


class AffiliationConfirmedMessage(Email):

    def __init__(self, user: UserRegistered, team: Team):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} affiliation confirmed'
        self.message.set_content(
            f'Hi {user.fullname}. '
            f'Your affiliation with {team.fullname} has been confirmed. '
            'You can now access data submitted by users that registered with this team.'
        )


class AdminGrantedMessage(Email):

    def __init__(self, user: UserRegistered, team: Team):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} admin granted'
        self.message.set_content(
            f'Hi {user.fullname}. '
            f'Your administrator status for {team.fullname} has been confirmed. '
            'You can now control access to data submitted by users that registered with this team. '
            'You can also allow new users to register by adding their email address to those allowed. '
        )
