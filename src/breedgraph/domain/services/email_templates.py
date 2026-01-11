import json
import logging

from src.breedgraph.config import SITE_NAME
from src.breedgraph.domain.model.accounts import UserBase
from src.breedgraph.domain.model.organisations import Access, TeamBase
from src.breedgraph.config import get_base_url
from email.message import EmailMessage


logger = logging.getLogger(__name__)

class Email:

    def __init__(self):
        self.message = EmailMessage()


class EmailAddedMessage(Email):

    def __init__(self, ):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} registration now available'
        self.message.set_content(
            f'Welcome to {SITE_NAME}\n'
            f'You are now able to register with this email address.'
            f'Visit the following address to get started: {get_base_url()}'
        )

class VerifyEmailMessage(Email):

    def __init__(self, user: UserBase, token: str):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} account email verification'
        verify_url = f'{get_base_url()}verify'
        body = (
            f'Hi {user.fullname}, \n'
            f'Please visit the following link to verify your email address: \n'
            f'{verify_url + "?token=" + token}'
        )
        self.message.set_content(body)
        self.message.add_attachment(
            json.dumps({"token": token}).encode('utf-8'),
            maintype='application',
            subtype='json',
            filename='verify_email_token.json'
        )

class ResetPasswordMessage(Email):

    def __init__(self, user: UserBase, token: str):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} account reset password'
        reset_url = f'{get_base_url()}reset'
        body = (
            f'Hi {user.fullname}, \n'
            f'Please visit the following link to reset your password address: \n'
            f'{reset_url + "?token=" + token}'
        )
        self.message.set_content(body)
        self.message.add_attachment(
            json.dumps({"token": token}).encode('utf-8'),
            maintype='application',
            subtype='json',
            filename='reset_password_token.json'
        )

class AffiliationRequestedMessage(Email):

    def __init__(self, requesting_user: UserBase, team: TeamBase, access: Access):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} {access.name.casefold()} access requested'
        body = (
            f'Admin notification:\n'
            f'{requesting_user.fullname} requested {access.name.casefold()} access to {team.name}.\n'
            f'Please consider authorising this request.'
        )
        self.message.set_content(body)


class AffiliationApprovedMessage(Email):

    def __init__(self, user: UserBase, team: TeamBase, access: Access):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} {access.name.casefold()} access approved'
        body = (
            f'Hi {user.fullname},\n'
            f'Your account was approved for {access.name.casefold()} access to {team.name}.\n'
        )
        self.message.set_content(body)

class FileUploadSuccess(Email):

    def __init__(self, user: UserBase, filename: str, reference_id: int):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} file upload success notification'
        body = (
            f'Hi {user.fullname}, \n'
            f'Your file upload ({filename}) was successfully completed and linked to reference {reference_id}'
        )
        self.message.set_content(body)


class FileUploadFailed(Email):

    def __init__(self, user: UserBase, filename: str, reference_id: int):
        super().__init__()
        self.message['SUBJECT'] = f'{SITE_NAME} file upload failure notification'
        body = (
            f'Hi {user.fullname}, \n'
            f'Your file upload ({filename}) failed for reference {reference_id}'
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
