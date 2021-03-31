from typing import Dict, Type, Callable
from dbtools.domain import commands

from . import accounts

COMMAND_HANDLERS = {
    commands.accounts.Initialise: accounts.initialise,
    commands.accounts.AddEmail: accounts.add_email,
    commands.accounts.RemoveEmail: accounts.remove_email,
    commands.accounts.AddAccount: accounts.add_account,
    commands.accounts.AddAffiliation: accounts.add_affiliation,
    commands.accounts.ConfirmUser: accounts.confirm_user_email,
    commands.accounts.SetAffiliationLevel: accounts.set_affiliation_level,
    commands.accounts.Login: accounts.login
}  # type: Dict[Type[commands.base.Command], Callable]
