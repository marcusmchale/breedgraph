from typing import Dict, Type, Callable
from src.dbtools.domain import commands

from . import accounts, setup

COMMAND_HANDLERS = {
    # commands.setup.EnsureGlobalAdmin: setup.ensure_global_admin,
    commands.setup.LoadReadModel: setup.load_read_model,
    commands.accounts.AddAccount: accounts.add_account,
    commands.accounts.AddEmail: accounts.add_email,
    commands.accounts.RemoveEmail: accounts.remove_email,
    commands.accounts.SetAffiliation: accounts.set_affiliation,
    commands.accounts.ConfirmUser: accounts.confirm_user_email,
    commands.accounts.Login: accounts.login
}  # type: Dict[Type[commands.base.Command], Callable]
