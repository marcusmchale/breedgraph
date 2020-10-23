from dbtools.domain.commands import AddAccount, ConfirmUser
from flask_bcrypt import Bcrypt

from . import graphql_query, graphql_mutation

from dbtools.entrypoints.flask_app import app, bus


@graphql_query.field("get_account")
def get_account(_, info, username):
	with bus.uow as uow:
		return uow.accounts.get(username.casefold())


@graphql_mutation.field("add_account")
def add_account(
	_,
	info,
	username: str,
	fullname: str,
	email: str,
	password: str,
	team_name: str
):
	password_hash = Bcrypt(app).generate_password_hash(password)
	cmd = AddAccount(username, fullname, password_hash, email, team_name)
	bus.handle(cmd)
	return True


@graphql_mutation.field("confirm_user")
def confirm_user(
	_,
	info,
	token: str
):
	bus.handle(ConfirmUser(token))
	return True

