from ariadne import ObjectType

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_programs_map,
    update_ontology_map
)

from src.breedgraph.domain.model.programs import ProgramOutput, TrialOutput, StudyOutput

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
program = ObjectType("Program")
trial = ObjectType("Trial")
study = ObjectType("Study")
graphql_resolvers.register_type_resolvers(program, trial, study)

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

@program.field("trials")
def resolve_trials(obj, info) -> List[TrialOutput]:
    return obj.trials.values()

@trial.field("name")
def resolve_trial_name(obj, info) -> int | None:
    return obj.name

@trial.field("studies")
def resolve_studies(obj, info) -> List[StudyOutput]:
    return obj.studies.values()

