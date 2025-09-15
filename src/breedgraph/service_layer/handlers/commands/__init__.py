from typing import Dict, Type, Callable
from src.breedgraph.domain import commands

from . import regions, organisations, accounts, setup, ontologies, blocks, datasets, arrangements, programs

#COMMAND_HANDLERS = {
#    commands.setup.LoadReadModel: setup.load_read_model,
#
#    commands.accounts.UpdateUser: accounts.edit_user,
#    commands.accounts.AddEmail: accounts.add_email,
#    commands.accounts.RemoveEmail: accounts.remove_email,
#    commands.accounts.VerifyEmail: accounts.verify_email,
#    commands.accounts.Login: accounts.login,
#    commands.accounts.RequestAffiliation: accounts.request_affiliation,
#    commands.accounts.ApproveAffiliation: accounts.approve_affiliation,
#    commands.accounts.RemoveAffiliation: accounts.remove_affiliation,
#    commands.accounts.RevokeAffiliation: accounts.revoke_affiliation,
#    commands.organisations.CreateTeam: organisations.create_team,
#    commands.organisations.DeleteTeam: organisations.delete_team,
#    commands.organisations.UpdateTeam: organisations.update_team,
#    commands.regions.CreateLocation: regions.add_location,
#    commands.ontologies.CreateOntologyEntry: ontologies.add_ontology_entry,
#    commands.blocks.CreateUnit: blocks.create_unit,
#    commands.blocks.AddPosition: blocks.add_position,
#    commands.datasets.CreateDataSet: datasets.add_dataset,
#    commands.datasets.AddRecord: datasets.add_record,
#    commands.arrangements.CreateLayout: arrangements.add_layout,
#    commands.programs.CreateProgram: programs.create_program,
#    commands.programs.UpdateProgram: programs.update_program,
#    commands.programs.DeleteProgram: programs.delete_program
#}  # type: Dict[Type[commands.base.Command], Callable]
