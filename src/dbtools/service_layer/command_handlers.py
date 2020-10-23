from itsdangerous import URLSafeTimedSerializer
from dbtools import config
from dbtools.service_layer import unit_of_work
from dbtools.domain import commands, events
from dbtools.domain.model import User, Affiliation, AffiliationLevel, Affiliations, Account
from dbtools.custom_exceptions import (
	NoResultFoundError,
	IdentityExistsError,
	ProtectedNodeError,
	UnauthorisedOperationError
)
from typing import Dict, Type, Callable


def add_email(
		cmd: commands.AddEmail,
		uow: unit_of_work.AbstractUnitOfWork
):
	with uow:
		account = uow.accounts.get(cmd.admin_username_lower)
		if not account.is_admin():
			raise UnauthorisedOperationError
		uow.emails.add(account.user, cmd.user_email)
		account.events.append(events.EmailAdded(cmd.user_email))
		uow.commit()


def remove_email(
		cmd: commands.RemoveEmail,
		uow: unit_of_work.AbstractUnitOfWork
):
	with uow:
		account = uow.accounts.get(cmd.admin_username_lower)
		if not account.is_admin():
			raise UnauthorisedOperationError
		uow.emails.remove(account.user, cmd.user_email)
		uow.commit()


def add_account(
		cmd: commands.AddAccount,
		uow: unit_of_work.AbstractUnitOfWork
):
	with uow:
		if not uow.emails.get(cmd.user_email):
			raise UnauthorisedOperationError
		account_by_email = uow.accounts.get_by_email(cmd.user_email)
		if account_by_email:
			if account_by_email.user.confirmed:
				raise ProtectedNodeError
			else:
				uow.accounts.remove(account_by_email)
		if uow.accounts.get(cmd.username):
			raise IdentityExistsError
		user = User(
			username=cmd.username,
			fullname=cmd.fullname,
			password_hash=cmd.password_hash,
			email=cmd.user_email
		)
		team = uow.teams.get(cmd.team_name)
		affiliation = Affiliation(team, AffiliationLevel(0))
		account = Account(
			user,
			Affiliations(affiliation)
		)
		uow.accounts.add(account)
		account.events.append(events.AccountAdded(username_lower=user.username_lower))
		uow.commit()


def confirm_user(
		cmd: commands.ConfirmUser,
		uow: unit_of_work.AbstractUnitOfWork
):
	with uow:
		ts = URLSafeTimedSerializer(config.SECRET_KEY)
		user_name_lower = ts.loads(cmd.token, salt=config.CONFIRM_TOKEN_SALT, max_age=86400)
		user = uow.accounts.get(user_name_lower)
		if not user:
			raise NoResultFoundError
		user.confirmed = True
		uow.commit()


def add_affiliation(
		cmd: commands.AddAffiliation,
		uow: unit_of_work.AbstractUnitOfWork
):
	with uow:
		account = uow.accounts.get(cmd.username_lower)
		team = uow.teams.get(cmd.team_name)
		affiliation = Affiliation(team, AffiliationLevel(0))
		account.affiliations.append(affiliation)


def set_affiliation_level(
		cmd: commands.SetAffiliationLevel,
		uow: unit_of_work.AbstractUnitOfWork
):
	with uow:
		account = uow.accounts.get(cmd.username_lower)
		affiliation = account.affiliations.get_by_team_name(cmd.team_name)
		affiliation.level = AffiliationLevel(cmd.level)


COMMAND_HANDLERS = {
	commands.AddEmail: add_email,
	commands.RemoveEmail: remove_email,
	commands.AddAccount: add_account,
	commands.AddAffiliation: add_affiliation,
	commands.ConfirmUser: confirm_user,
	commands.SetAffiliationLevel: set_affiliation_level
}  # type: Dict[Type[commands.Command], Callable]
