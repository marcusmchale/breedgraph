from ariadne import ObjectType

from src.breedgraph.domain.model import LegalReferenceStored, DesignOutput
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_ontology_map,
    update_reference_map
)
from src.breedgraph.domain.model.programs import ProgramOutput, TrialOutput, StudyOutput

from src.breedgraph.domain.model.references import ReferenceStoredBase


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
        info
) -> List[ProgramOutput]:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        programs = [p.to_output() async for p in uow.repositories.programs.get_all()]
        return programs

@graphql_query.field("programsProgram")
@graphql_payload
@require_authentication
async def get_program(
        _,
        info,
        program_id: int | None = None,
        trial_id: int | None = None,
        study_id: int | None = None
) -> ProgramOutput:
    if not program_id or trial_id or study_id:
        raise ValueError("Program, Trial or Study ID required to fetch a program")
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        program_stored = await uow.repositories.programs.get(program_id=program_id, trial_id=trial_id, study_id=study_id)
        return program_stored.to_output()

@graphql_query.field("programsTrial")
@graphql_payload
@require_authentication
async def get_trial(
        _,
        info,
        trial_id: int | None = None,
        study_id: int | None = None
) -> TrialOutput:
    if not trial_id or study_id:
        raise ValueError("Trial or Study ID required to fetch a trial")
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        program_stored = await uow.repositories.programs.get(trial_id=trial_id, study_id=study_id)
        trial_stored = program_stored.get_trial(trial_id=trial_id, study_id=study_id)
        return trial_stored.to_output()

@graphql_query.field("programsStudy")
@graphql_payload
@require_authentication
async def get_study(
        _,
        info,
        study_id: int
) -> StudyOutput:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        program_stored = await uow.repositories.programs.get(study_id=study_id)
        study_stored = program_stored.get_study(study_id=study_id)
        return study_stored.to_output()


@program.field("trials")
def resolve_trials(obj, info) -> List[TrialOutput]:
    return obj.trials.values()

@trial.field("studies")
def resolve_studies(obj, info) -> List[StudyOutput]:
    return obj.studies.values()

@program.field("references")
async def resolve_references(obj, info) -> List[ReferenceStoredBase]:
    await update_reference_map(info.context, reference_ids = obj.reference_ids)
    reference_map = info.context.get('reference_map')
    return [reference_map.get(refId) for refId in obj.reference_ids if refId in reference_map]

@trial.field("references")
async def resolve_references(obj, info) -> List[ReferenceStoredBase]:
    await update_reference_map(info.context, reference_ids = obj.reference_ids)
    reference_map = info.context.get('reference_map')
    return [reference_map.get(refId) for refId in obj.reference_ids if refId in reference_map]

@study.field("references")
async def resolve_references(obj, info) -> List[ReferenceStoredBase]:
    await update_reference_map(info.context, reference_ids = obj.reference_ids)
    reference_map = info.context.get('reference_map')
    return [reference_map.get(refId) for refId in obj.reference_ids if refId in reference_map]

@study.field("licence")
async def resolve_licence(obj, info) -> LegalReferenceStored | None:
    if not obj.licence_id:
        return None
    await update_reference_map(info.context, reference_ids = [obj.licence_id])
    reference_map = info.context.get('reference_map')
    return reference_map.get(obj.licence_id)

@study.field("design")
async def resolve_design(obj, info) -> DesignOutput:
    if not obj.design_id:
        return None
    await update_ontology_map(context = info.context, entry_ids=[obj.design_id])
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.design_id)