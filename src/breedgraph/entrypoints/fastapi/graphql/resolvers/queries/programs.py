from ariadne import ObjectType

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_programs_map,
    inject_ontology
)
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.controls import resolve_controller

from src.breedgraph.domain.model.programs import ProgramOutput, TrialStored, StudyStored # todo consider changing to output
from src.breedgraph.domain.model.controls import Controller

from typing import List

import logging
logger = logging.getLogger(__name__)

program = ObjectType("Program")
trial = ObjectType("Trial")
study = ObjectType("Study")

@graphql_query.field("programs")
@graphql_payload
@require_authentication
async def get_programs(
        _,
        info,
        program_id: int | None = None,
        trial_id: int | None = None,
        study_id: int | None = None
) -> List[ProgramOutput]:
    await update_programs_map(info.context, program_id=program_id, trial_id=trial_id, study_id=study_id)
    programs_map = info.context.get('programs_map')
    return programs_map.values()

@program.field("controller")
async def resolve_program_controller(obj, info) -> Controller:
    controller = await resolve_controller(obj, info)
    return controller

@program.field("trials")
def resolve_trials(obj, info) -> List[TrialStored]:
    return obj.trials.values()
    #import pdb; pdb.set_trace()
    #return info.context.get('programs_map').get(obj.id).trials

@trial.field("studies")
def resolve_studies(obj, info) -> List[StudyStored]:
    return obj.studies.values()
    #return info.context.get('programs_map').get(obj.program).trials.get(obj.id).studies

