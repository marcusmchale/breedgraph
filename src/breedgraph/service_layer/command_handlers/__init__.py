from typing import Dict, Type, Callable
from src.breedgraph.domain import commands

from . import regions, organisations, accounts, setup, ontologies

COMMAND_HANDLERS = {
    commands.setup.LoadReadModel: setup.load_read_model,
    commands.accounts.AddAccount: accounts.add_account,
    commands.accounts.UpdateUser: accounts.edit_user,
    commands.accounts.AddEmail: accounts.add_email,
    commands.accounts.RemoveEmail: accounts.remove_email,
    commands.accounts.VerifyEmail: accounts.verify_email,
    commands.accounts.Login: accounts.login,
    commands.accounts.RequestAffiliation: accounts.request_affiliation,
    commands.accounts.ApproveAffiliation: accounts.approve_affiliation,
    commands.accounts.RemoveAffiliation: accounts.remove_affiliation,
    commands.organisations.AddTeam: organisations.add_team,
    commands.organisations.RemoveTeam: organisations.remove_team,
    commands.organisations.UpdateTeam: organisations.edit_team,
    commands.regions.AddLocation: regions.add_location,
    commands.ontologies.AddOntologyEntry: ontologies.add_ontology_entry
}  # type: Dict[Type[commands.base.Command], Callable]
