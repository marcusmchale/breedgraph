from typing import Dict, Type, Callable
from src.breedgraph.domain import commands

from . import regions, organisations, accounts, setup, ontologies, blocks, datasets, arrangements

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
    commands.accounts.RevokeAffiliation: accounts.revoke_affiliation,
    commands.organisations.AddTeam: organisations.add_team,
    commands.organisations.RemoveTeam: organisations.remove_team,
    commands.organisations.UpdateTeam: organisations.edit_team,
    commands.regions.AddLocation: regions.add_location,
    commands.ontologies.AddOntologyEntry: ontologies.add_ontology_entry,
    commands.blocks.AddUnit: blocks.add_unit,
    commands.blocks.AddPosition: blocks.add_position,
    commands.datasets.AddDataSet: datasets.add_dataset,
    commands.datasets.AddRecord: datasets.add_record,
    commands.arrangements.AddLayout: arrangements.add_layout
}  # type: Dict[Type[commands.base.Command], Callable]
