from itsdangerous import URLSafeTimedSerializer
from flask import url_for
from dbtools import config
from dbtools.adapters.notifications import notifications
from dbtools.service_layer import unit_of_work
from dbtools.domain import events
from dbtools.custom_exceptions import (
	NoResultFoundError
)
from dbtools.adapters.notifications import messages

from typing import Dict, Type, List, Callable


def email_user_allowed(
		event: events.EmailAdded,
		notifications: notifications.EmailNotifications
):
	# send allowed user a simple email with link to registration address
	notifications.send_basic_email(
		[event.email],
		messages.EmailAddedMessage()
	)


def send_user_confirm_url(
		event: events.AccountAdded,
		uow: unit_of_work.AbstractUnitOfWork,
		notifications: notifications.AbstractNotifications
):
	with uow:
		account = uow.accounts.get(event.username_lower)
		if not account:
			raise NoResultFoundError
		token = URLSafeTimedSerializer(config.SECRET_KEY).dumps(
			account.user.username_lower,
			salt=config.CONFIRM_TOKEN_SALT
		)
		message = messages.UserConfirmMessage(
			account.user,
			token=token
		)
		notifications.send(
			[account.user],
			message
		)


def send_confirmed_notification(
		event: events.AffiliationConfirmed,
		uow: unit_of_work.AbstractUnitOfWork,
		notifications: notifications.AbstractNotifications
):
	with uow:
		account = uow.accounts.get(event.username_lower)
		team = uow.teams.get(event.team_name)
		if not account:
			raise NoResultFoundError
		message = messages.AffiliationConfirmedMessage(
			account.user,
			team
		)
		notifications.send(
			[account.user],
			message
		)


def send_admin_notification(
		event: events.AdminGranted,
		uow: unit_of_work.AbstractUnitOfWork,
		notifications: notifications.AbstractNotifications
):
	with uow:
		account = uow.accounts.get(event.username_lower)
		team = uow.teams.get(event.team_name)
		if not account:
			raise NoResultFoundError
		message = messages.AdminGrantedMessage(
			account.user,
			team
		)
		notifications.send(
			[account.user],
			message
		)


EVENT_HANDLERS = {
	events.EmailAdded: [email_user_allowed],
	events.AccountAdded: [send_user_confirm_url],
	events.AffiliationConfirmed: [send_confirmed_notification],
	events.AdminGranted: [send_admin_notification]
}  # type: Dict[Type[events.Event], List[Callable]]
