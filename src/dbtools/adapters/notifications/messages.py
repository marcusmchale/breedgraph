from flask_mail import Message

from dbtools.config import SITE_NAME
from flask import url_for
from dbtools.domain.model import User, Team


class EmailAddedMessage(Message):

	def __init__(self):
		super().__init__()
		self.subject = f'{SITE_NAME} registration now available'
		self.body = (
			f'Welcome to {SITE_NAME}. \n'
			f'You are now able to register with this email address at the following address: {url_for("graphql")}'
		)


class UserConfirmMessage(Message):

	def __init__(self, user: User, token: str):
		super().__init__()
		self.subject = f'{SITE_NAME} account confirmation'
		# options here are a url to a rest endpoint or handle the token posted over graphql
		# this can be done through a form submission disguised as a link but this wouldn't work without html
		# for ease of use for users without html email we have a rest endpoint just for this url
		self.body = (
			f'Hi {user.fullname}. '
			f'Please visit the following link to confirm your registration: '
			f'{url_for("confirm_account", token=token, _external=True)}\n'
		)


class AffiliationConfirmedMessage(Message):

	def __init__(self, user: User, team: Team):
		super().__init__()
		self.subject = f'{SITE_NAME} affiliation confirmed'
		self.body = (
			f'Hi {user.fullname}. '
			f'Your affiliation with {team.fullname} has been confirmed. '
			'You can now access data submitted by users that registered with this team.'
		)


class AdminGrantedMessage(Message):

	def __init__(self, user: User, team: Team):
		super().__init__()
		self.subject = f'{SITE_NAME} admin granted'
		self.body = (
			f'Hi {user.fullname}. '
			f'Your administrator status for {team.fullname} has been confirmed. '
			'You can now control access to data submitted by users that registered with this team. '
			'You can also allow new users to register by adding their email address to those allowed. '
		)
