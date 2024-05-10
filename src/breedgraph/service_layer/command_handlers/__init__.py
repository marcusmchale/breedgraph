from typing import Dict, Type, Callable
from src.breedgraph.domain import commands

from . import locations, accounts, setup

COMMAND_HANDLERS = {
    commands.setup.LoadReadModel: setup.load_read_model,
    commands.accounts.AddFirstAccount: accounts.add_first_account,
    commands.accounts.AddAccount: accounts.add_account,
    commands.accounts.AddEmail: accounts.add_email,
    commands.accounts.RemoveEmail: accounts.remove_email,
    commands.accounts.VerifyEmail: accounts.verify_email,
    commands.accounts.Login: accounts.login,
    commands.accounts.AddTeam: accounts.add_team,
    commands.accounts.RemoveTeam: accounts.remove_team,
    commands.accounts.RequestAffiliation: accounts.request_affiliation,
    commands.accounts.ApproveAffiliation: accounts.approve_affiliation,
    commands.accounts.RemoveAffiliation: accounts.remove_affiliation,
    commands.accounts.AddCountry: locations.add_country,
}  # type: Dict[Type[commands.base.Command], Callable]
