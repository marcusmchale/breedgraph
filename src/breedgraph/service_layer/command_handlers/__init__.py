from typing import Dict, Type, Callable
from src.breedgraph.domain import commands

from . import locations, organisations, accounts, setup, ontologies

COMMAND_HANDLERS = {
    commands.setup.LoadReadModel: setup.load_read_model,
    commands.accounts.AddFirstAccount: accounts.add_first_account,
    commands.accounts.AddAccount: accounts.add_account,
    commands.accounts.AddEmail: accounts.add_email,
    commands.accounts.RemoveEmail: accounts.remove_email,
    commands.accounts.VerifyEmail: accounts.verify_email,
    commands.accounts.Login: accounts.login,
    commands.accounts.RequestAffiliation: accounts.request_affiliation,
    commands.accounts.ApproveAffiliation: accounts.approve_affiliation,
    commands.accounts.RemoveAffiliation: accounts.remove_affiliation,
    commands.organisations.AddTeam: organisations.add_team,
    commands.organisations.RemoveTeam: organisations.remove_team,
    commands.organisations.EditTeam: organisations.edit_team,
    commands.countries.AddCountry: locations.add_country,
    commands.ontologies.AddTerm: ontologies.add_term
}  # type: Dict[Type[commands.base.Command], Callable]
