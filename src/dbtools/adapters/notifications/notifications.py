import abc
from typing import List
from dbtools.domain.model import User
from dbtools.adapters.notifications.messages import Message

from flask_mail import Mail


class AbstractNotifications(abc.ABC):

	@abc.abstractmethod
	def send(
		self,
		recipients: List[User],
		message: Message
	):
		raise NotImplementedError


class EmailNotifications(AbstractNotifications):

	def __init__(self, app):
		self.mail = Mail(app)

	def send(self, recipients: List[User], message: Message):
		message.recipients = [user.email for user in recipients]
		self.mail.send(message)

	def send_basic_email(self, emails: List[str], message: Message):
		message.recipients = emails
		self.mail.send(message)
