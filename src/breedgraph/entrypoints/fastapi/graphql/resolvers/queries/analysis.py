from ariadne import ObjectType

from src.breedgraph.adapters.redis.state_store import SubmissionStatus

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

factor_level = ObjectType("FactorLevel")
group_summary = ObjectType("GroupSummary")
analysis_submission = ObjectType("AnalysisSubmission")
analysis_result = ObjectType("AnalysisResult")
analysis_config = ObjectType("AnalysisConfig")

graphql_resolvers.register_type_resolvers(group_summary, analysis_submission, analysis_result)

"""Submission resolver"""
@graphql_query.field("analysisSubmission")
@graphql_payload
@require_authentication
async def get_submission(_, info, analysis_id: str):
    return analysis_id

@analysis_submission.field('status')
async def resolve_status(analysis_id: str, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    status = await bus.state_store.get_status(agent_id=user_id, key=analysis_id)
    return status


@analysis_submission.field('errors')
async def resolve_errors(analysis_id: str, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    errors = await bus.state_store.get_errors(agent_id=user_id, key=analysis_id)
    return errors

@analysis_submission.field('result')
async def resolve_result(analysis_id: str, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    result = await bus.state_store.get_analysis_result(agent_id=user_id, analysis_id=analysis_id)
    return {'analysis_id':analysis_id, 'result':result }

@analysis_result.field('config')
async def resolve_config(result: dict, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    config = await bus.state_store.get_analysis_config(agent_id=user_id, analysis_id=result.get('analysis_id'))
    return config

@analysis_config.field('datasetIds')
async def resolve_dataset_ids(config: dict, info):
    return config.get('dataset_ids')

@analysis_config.field('dependentVariable')
async def resolve_dependent_variable(config: dict, info):
    return config.get('dependent_variable')

@analysis_config.field('independentVariables')
async def resolve_independent_variables(config: dict, info):
    return config.get('independent_variables')

@analysis_config.field('interactionTerms')
async def resolve_interaction_terms(config: dict, info):
    return config.get('interaction_terms')

@analysis_config.field('timepointBoundaries')
async def resolve_timepoint_boundaries(config: dict, info):
    return config.get('timepoint_boundaries')

@analysis_config.field('name')
async def resolve_analysis_name(config: dict, info):
    name = config.get('name')
    if not name:
        name = config.get('dependent_variable').get('label')
    return name

@analysis_result.field('anova')
async def resolve_anova(result: dict, info):
    result = result.get('result')
    if result:
        anova_data = result.get('anova')
        return anova_data
    return None

@analysis_result.field('group')
async def resolve_group(result:dict, info):
    result = result.get('result')
    if result:
        return result.get('group')
    return None

@analysis_result.field('tukey')
async def resolve_tukey(result:dict, info):
    result = result.get('result')
    if result:
        return result.get('tukey')
    return None