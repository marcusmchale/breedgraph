from ariadne import ObjectType

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.ontology import resolve_ontology_entries

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

analysis_submission = ObjectType("AnalysisSubmission")
analysis_result = ObjectType("AnalysisResult")
analysis_config = ObjectType("AnalysisConfig")
analysis_term = ObjectType("AnalysisTerm")
analysis_term_reference = ObjectType("AnalysisTermReference")

graphql_resolvers.register_type_resolvers(
    analysis_submission, analysis_result, analysis_config,
    analysis_term, analysis_term_reference
)



@graphql_query.field("analysisSubmission")
@graphql_payload
@require_authentication
async def get_submission(_, info, id_: str):
    """Return analysis_id for field resolution"""
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    await bus.state_store.verify_agent(agent_id=user_id, key=id_)
    return id_

@analysis_submission.field('status')
async def resolve_status(analysis_id: str, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    status = await bus.state_store.get_status(agent_id=user_id, key=analysis_id)
    return status

@analysis_submission.field('config')
async def resolve_config(analysis_id: str, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    config = await bus.state_store.get_analysis_config(agent_id=user_id, analysis_id=analysis_id)
    return config

@analysis_submission.field('result')
async def resolve_result(analysis_id: str, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    result = await bus.state_store.get_analysis_result(agent_id=user_id, analysis_id=analysis_id)
    return result

@analysis_submission.field('errors')
async def resolve_errors(analysis_id: str, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    errors = await bus.state_store.get_analysis_errors(agent_id=user_id, analysis_id=analysis_id)
    return errors or []

@analysis_submission.field('warnings')
async def resolve_warnings(analysis_id: str, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    warnings = await bus.state_store.get_analysis_warnings(agent_id=user_id, analysis_id=analysis_id)
    return warnings or []

@analysis_config.field('name')
async def resolve_analysis_name(config: dict, info):
    name = config.get('name')
    if not name and config.get('dependent_variable'):
        name = config.get('dependent_variable').get('label')
    return name

@analysis_term.field('ontologyEntry')
async def resolve_ontology_entry(term: dict, info):
    """Resolve ontology entry for CONCEPT terms"""
    reference = term.get('reference', {})
    if reference.get('type') != 'CONCEPT':
        return None

    concept_id = reference.get('concept_id')
    if not concept_id:
        return None

    entries = await resolve_ontology_entries(info.context, entry_ids=[concept_id])
    return entries[0] if entries else None