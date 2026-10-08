import json
from datetime import datetime

from breedgraph.config import SITE_NAME
from breedgraph.domain.model import FileReferenceBase, Access
from breedgraph.domain.model.accounts import UserBase
from breedgraph.domain.model.organisations import TeamBase
from breedgraph.domain.model.archive import ArchiveRequestor
from breedgraph.config import PROTOCOL, HOST_ADDRESS
from email.message import EmailMessage

import logging

logger = logging.getLogger(__name__)

class Email:

    def __init__(self):
        self.message = EmailMessage()


class PersonClaimRequestedMessage(Email):

    def __init__(self, requesting_user: UserBase, person_id: int):
        super().__init__()
        self.message['Subject'] = f'{SITE_NAME} request to link a Person record'
        body = (
            f'Admin notification:\n'
            f'{requesting_user.fullname} asked to link their account to Person record {person_id}.\n'
            f'Please confirm their identity before approving the request at {PROTOCOL}://{HOST_ADDRESS}.'
        )
        self.message.set_content(body)


class PersonLinkedMessage(Email):

    def __init__(self, user: UserBase):
        super().__init__()
        self.message['Subject'] = f'{SITE_NAME} Person record linked to your account'
        body = (
            f'Hi {user.fullname},\n'
            f'A Person record used to credit your contributions is now linked to your account.\n'
            f'You can view, correct, unlink or erase it at {PROTOCOL}://{HOST_ADDRESS}.\n'
            f'If the Person is listed as a contact, other users may message you through {SITE_NAME}. '
            f'Messages arrive at this email address, which senders never see. '
            f'You can remove yourself as a contact at any time.'
        )
        self.message.set_content(body)


class InvitationMessage(Email):

    def __init__(self, inviter: UserBase, token: str, expires_at: datetime, offers_affiliation: bool):
        super().__init__()
        self.message['Subject'] = f'Invitation to register with {SITE_NAME}'
        register_url = f'{PROTOCOL}://{HOST_ADDRESS}/register?token={token}'
        body = (
            f'{inviter.fullname} has invited you to register with {SITE_NAME}.\n'
            + (f'The invitation includes access to their teams, which you can accept or decline when registering.\n'
               if offers_affiliation else '')
            + f'Register using this email address at: \n'
            f'{register_url}\n'
            f'The invitation expires on {expires_at:%Y-%m-%d}. '
            f'If you do not register, your email address is deleted when it expires.'
        )
        self.message.set_content(body)
        self.message.add_attachment(
            json.dumps({"token": token}).encode('utf-8'),
            maintype='application',
            subtype='json',
            filename='invitation_token.json'
        )


class VerifyEmailMessage(Email):

    def __init__(self, user: UserBase, token: str):
        super().__init__()
        self.message['Subject'] = f'{SITE_NAME} account email verification'
        verify_url = f'{PROTOCOL}://{HOST_ADDRESS}/verify'
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
        self.message['Subject'] = f'{SITE_NAME} account reset password'
        reset_url = f'{PROTOCOL}://{HOST_ADDRESS}/reset'
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
        self.message['Subject'] = f'{SITE_NAME} {access.name.casefold()} access requested'
        body = (
            f'Admin notification:\n'
            f'{requesting_user.fullname} requested {access.name.casefold()} access to {team.name}.\n'
            f'Please consider authorising this request.'
        )
        self.message.set_content(body)


class AffiliationApprovedMessage(Email):

    def __init__(self, user: UserBase, team: TeamBase, access: Access):
        super().__init__()
        self.message['Subject'] = f'{SITE_NAME} {access.name.casefold()} access approved'
        body = (
            f'Hi {user.fullname},\n'
            f'Your account was approved for {access.name.casefold()} access to {team.name}.\n'
        )
        self.message.set_content(body)

class ControlTransferOfferedMessage(Email):

    def __init__(self, offering_user: UserBase, team: TeamBase, entity_count: int):
        super().__init__()
        self.message['Subject'] = f'{SITE_NAME} control transfer offered to {team.name}'
        body = (
            f'Admin notification:\n'
            f'{offering_user.fullname} offered control of {entity_count} '
            f'{"entry" if entity_count == 1 else "entries"} to {team.name}.\n'
            f'Please review the offer at {PROTOCOL}://{HOST_ADDRESS}.'
        )
        self.message.set_content(body)


class FileUploadSuccess(Email):

    def __init__(self, user: UserBase, filename: str, reference_id: int):
        super().__init__()
        self.message['Subject'] = f'{SITE_NAME} file upload success notification'
        body = (
            f'Hi {user.fullname}, \n'
            f'Your file upload ({filename}) was successfully completed and linked to reference {reference_id}'
        )
        self.message.set_content(body)


class FileUploadFailed(Email):

    def __init__(self, user: UserBase, filename: str, reference_id: int):
        super().__init__()
        self.message['Subject'] = f'{SITE_NAME} file upload failure notification'
        body = (
            f'Hi {user.fullname}, \n'
            f'Your file upload ({filename}) failed for reference {reference_id}'
        )
        self.message.set_content(body)

#class AffiliationConfirmedMessage(Email):
#
#    def __init__(self, user: UserBase, team: TeamBase):
#        super().__init__()
#        self.message['Subject'] = f'{SITE_NAME} affiliation confirmed'
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
#        self.message['Subject'] = f'{SITE_NAME} admin granted'
#        self.message.set_content(
#            f'Hi {user.fullname}. '
#            f'Your administrator status for {team.fullname} has been confirmed. '
#            'You can now control access to data submitted by users that registered with this key. '
#            'You can also allow new users to register by adding their email address to those allowed. '
#        )


class FileRetrievalSuccess(Email):
    """Notification that a file has been successfully retrieved from archive"""

    def __init__(self, requestor: ArchiveRequestor, reference: FileReferenceBase, url:str, expires: datetime):
        super().__init__()
        self.message['Subject'] = f"{SITE_NAME} file retrieved from archive"
        body = f"""
        Hi {requestor.name},
        You recently requested recovery of a file from the archive.
         It has now been retrieved and is available for download.
         
         Filename: {reference.filename}
         Download URL: {url}
         Expires: {expires.strftime(format="%Y-%m-%d %H:%M:%S")} 
        """
        self.message.set_content(body)


class FileRetrievalFailed(Email):
    """Notification that file retrieval from archive failed"""

    def __init__(self, requestor: ArchiveRequestor, file_id: str, error: str = ""):
        super().__init__()
        self.message['Subject'] = f"{SITE_NAME} file retrieval from archive failed"
        body = f"""
        Hi {requestor.name},
        Unfortunately, the retrieval of your requested file (ID: {file_id}) from the archive 
        has failed after multiple attempts.
        Error: {error}
        Please contact the system administrator for assistance.
        """
        self.message.set_content(body)
