from typing import Dict, Type, Callable
from src.breedgraph.domain import commands

from . import accounts, setup

COMMAND_HANDLERS = {
    # commands.setup.EnsureGlobalAdmin: setup.ensure_global_admin,
    commands.setup.LoadReadModel: setup.load_read_model,
    commands.accounts.AddFirstAccount: accounts.add_first_account,
    commands.accounts.AddAccount: accounts.add_account,
    commands.accounts.AddEmail: accounts.add_email,
    commands.accounts.RemoveEmail: accounts.remove_email,
    commands.accounts.VerifyEmail: accounts.verify_email,
    commands.accounts.Login: accounts.login,
    commands.accounts.AddTeam: accounts.add_team,
    commands.accounts.RemoveTeam: accounts.remove_team,
    commands.accounts.RequestRead: accounts.request_read,
    commands.accounts.AddRead: accounts.add_read,
    commands.accounts.RemoveRead: accounts.remove_read,
    #commands.accounts.RequestWrite: accounts.request_write,
    #commands.accounts.RequestAdmin: accounts.request_admin,
}  # type: Dict[Type[commands.base.Command], Callable]
