from ariadne import ObjectType

from breedgraph.custom_exceptions import NoResultFoundError

from breedgraph.service_layer.queries.read_models.ontology import (
    DesignOutput, RecordGroupTypeOutput,
    OntologyViewMode
)
from breedgraph.domain.model import LegalReferenceStored
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_ontology_map,
    update_reference_map,
    resolve_people
)
from breedgraph.domain.model.programs import ProgramOutput, TrialOutput, StudyOutput

from breedgraph.domain.model.references import ReferenceStoredBase


from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
program = ObjectType("Program")
trial = ObjectType("Trial")
study = ObjectType("Study")
record_grouping = ObjectType("RecordGrouping")
graphql_resolvers.register_type_resolvers(program, trial, study, record_grouping)

@graphql_query.field("programs")
@graphql_payload
async def get_programs(
        _,
        info
) -> List[ProgramOutput]:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.views_factory.get_views(user_id=user_id) as views:
        return [program.to_output() for program in await views.programs.get_programs()]

@graphql_query.field("programsProgram")
@graphql_payload
async def get_program(
        _,
        info,
        id: int | None = None,
        trial_id: int | None = None,
        study_id: int | None = None
) -> ProgramOutput:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.views_factory.get_views(user_id=user_id) as views:
        program_stored = await views.programs.get_program(program_id=id, trial_id=trial_id, study_id=study_id)
    if program_stored is None:
        raise NoResultFoundError("Program not found")
    return program_stored.to_output()

@graphql_query.field("programsTrial")
@graphql_payload
async def get_trial(
        _,
        info,
        id: int | None = None,
        study_id: int | None = None
) -> TrialOutput:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.views_factory.get_views(user_id=user_id) as views:
        trial_stored = await views.programs.get_trial(trial_id=id, study_id=study_id)
    if trial_stored is None:
        raise NoResultFoundError("Trial not found")
    return trial_stored.to_output()

@graphql_query.field("programsStudy")
@graphql_payload
async def get_study(
        _,
        info,
        id: int
) -> StudyOutput:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.views_factory.get_views(user_id=user_id) as views:
        study_stored = await views.programs.get_study(study_id=id)
    if study_stored is None:
        raise NoResultFoundError(f"Study {id} not found")
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
async def resolve_design(obj, info) -> DesignOutput | None:
    if not obj.design_id:
        return None
    await update_ontology_map(context = info.context, entry_ids=[obj.design_id], view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.design_id)

@record_grouping.field("type")
async def resolve_type(obj, info) -> RecordGroupTypeOutput:
    await update_ontology_map(context = info.context, entry_ids=[obj.type], view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.type)

@program.field("contacts")
async def resolve_program_contacts(obj, info):
    return await resolve_people(info.context, obj.contact_ids)

@trial.field("contacts")
async def resolve_trial_contacts(obj, info):
    return await resolve_people(info.context, obj.contact_ids)
