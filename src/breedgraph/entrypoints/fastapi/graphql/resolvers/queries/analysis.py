from ariadne import ObjectType, UnionType

from breedgraph.domain.model.analysis import AnalysisType
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

analysis_submission = ObjectType("AnalysisSubmission")
analysis_result = UnionType("AnalysisResult")
analysis_config = UnionType("AnalysisConfig")
analysis_term_reference = ObjectType("AnalysisTermReference")
analysis_grouping = ObjectType("AnalysisGrouping")
analysis_record_group_dimension = ObjectType("AnalysisRecordGroupDimension")
analysis_record_grouping = ObjectType("AnalysisRecordGrouping")
analysis_group = ObjectType("AnalysisGroup")

graphql_resolvers.register_type_resolvers(
    analysis_submission, analysis_result, analysis_config,
    analysis_term_reference,
    analysis_grouping, analysis_record_group_dimension,
    analysis_record_grouping, analysis_group
)

ANALYSIS_TYPE_KEY = '_analysis_type'
DIMENSION_KEY = '_record_group_dimension'

CONFIG_TYPES = {
    AnalysisType.ANOVA: "AnovaConfig",
    AnalysisType.MDS: "MDSConfig",
    AnalysisType.CORRELATION: "CorrelationConfig",
    AnalysisType.DESCRIPTIVE_STATISTICS: "DescriptiveStatisticsConfig",
    AnalysisType.OUTLIER_DETECTION: "OutlierDetectionConfig",
}
RESULT_TYPES = {
    AnalysisType.ANOVA: "AnovaResult",
    AnalysisType.MDS: "MDSResult",
    AnalysisType.CORRELATION: "CorrelationResult",
    AnalysisType.DESCRIPTIVE_STATISTICS: "DescriptiveStatisticsResult",
    AnalysisType.OUTLIER_DETECTION: "OutlierDetectionResult",
}


def _collect_record_group_dimensions(node, found: dict | None = None) -> dict[str, dict]:
    """Find record group dimensions (grouping.record_groups) anywhere in a stored input."""
    found = {} if found is None else found
    if isinstance(node, dict):
        grouping = node.get('grouping')
        if isinstance(grouping, dict):
            for dimension in grouping.get('record_groups') or []:
                found[dimension['name']] = dimension
        for value in node.values():
            _collect_record_group_dimensions(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_record_group_dimensions(value, found)
    return found


def _attach_record_group_dimensions(node, dimensions: dict[str, dict]):
    """Attach dimensions to RECORD_GROUP term references for field resolution."""
    if isinstance(node, dict):
        if node.get('type') == 'RECORD_GROUP' and 'record_group_dimension' in node:
            node[DIMENSION_KEY] = dimensions.get(node['record_group_dimension'])
        for key, value in node.items():
            if key != DIMENSION_KEY:
                _attach_record_group_dimensions(value, dimensions)
    elif isinstance(node, list):
        for value in node:
            _attach_record_group_dimensions(value, dimensions)
    return node


def _with_config_defaults(spec: dict) -> dict:
    """Defaults for optional input lists, which are non-null in the config types."""
    spec['interactions'] = spec.get('interactions') or []
    spec['estimated_means'] = spec.get('estimated_means') or []
    for means in spec['estimated_means']:
        means['by'] = means.get('by') or []
    for term in spec.get('terms') or []:
        term['transformations'] = term.get('transformations') or []
    position = (spec.get('grouping') or {}).get('position')
    if position is not None:
        position['positions'] = position.get('positions') or []
    return spec


@graphql_query.field("analysisSubmission")
@graphql_payload
@require_authentication
async def get_submission(_, info, id: str):
    """Return the stored analysis input for field resolution"""
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    analysis = await bus.state_store.get_analysis_config(agent_id=user_id, analysis_id=id)
    return {'analysis_id': id, 'input': analysis}

@graphql_query.field("analysisRecentSubmissions")
@graphql_payload
@require_authentication
async def get_recent_submissions(_, info):
    """Return the IDs of the user's unexpired analyses, most recently updated first"""
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    return await bus.state_store.get_user_analyses(agent_id=user_id)

@analysis_submission.field('id')
def resolve_id(submission: dict, info):
    return submission['analysis_id']

@analysis_submission.field('status')
async def resolve_status(submission: dict, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    return await bus.state_store.get_status(agent_id=user_id, key=submission['analysis_id'])

@analysis_submission.field('name')
def resolve_name(submission: dict, info):
    return submission['input'].get('name')

@analysis_submission.field('analysisType')
def resolve_analysis_type(submission: dict, info):
    return submission['input'].get('analysis_type')

@analysis_submission.field('datasetIds')
def resolve_dataset_ids(submission: dict, info):
    return submission['input'].get('dataset_ids') or []

@analysis_submission.field('exclusions')
def resolve_exclusions(submission: dict, info):
    return submission['input'].get('exclusions') or []

@analysis_submission.field('config')
def resolve_config(submission: dict, info):
    analysis = submission['input']
    analysis_type = AnalysisType(analysis['analysis_type'])
    spec = _with_config_defaults(dict(analysis.get(analysis_type.input_key) or {}))
    spec[ANALYSIS_TYPE_KEY] = analysis_type
    return _attach_record_group_dimensions(spec, _collect_record_group_dimensions(spec))

@analysis_submission.field('result')
async def resolve_result(submission: dict, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    result = await bus.state_store.get_analysis_result(agent_id=user_id, analysis_id=submission['analysis_id'])
    if result:
        _attach_record_group_dimensions(result, _collect_record_group_dimensions(submission['input']))
    return result

@analysis_submission.field('errors')
async def resolve_errors(submission: dict, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    return await bus.state_store.get_analysis_errors(agent_id=user_id, analysis_id=submission['analysis_id'])

@analysis_submission.field('warnings')
async def resolve_warnings(submission: dict, info):
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    return await bus.state_store.get_analysis_warnings(agent_id=user_id, analysis_id=submission['analysis_id'])


@analysis_config.type_resolver
def resolve_config_type(config: dict, *_):
    return CONFIG_TYPES[AnalysisType(config[ANALYSIS_TYPE_KEY])]

@analysis_result.type_resolver
def resolve_result_type(result: dict, *_):
    return RESULT_TYPES[AnalysisType(result['analysis_type'])]


@analysis_term_reference.field('recordGroupDimension')
def resolve_term_record_group_dimension(reference: dict, info):
    return reference.get(DIMENSION_KEY)

@analysis_grouping.field('recordGroups')
def resolve_grouping_record_groups(grouping: dict, info):
    return grouping.get('record_groups') or []

@analysis_record_group_dimension.field('groupings')
def resolve_dimension_groupings(dimension: dict, info):
    return [{'grouping_id': grouping_id} for grouping_id in dimension.get('grouping_ids') or []]

@analysis_record_group_dimension.field('levels')
def resolve_dimension_levels(dimension: dict, info):
    return dimension.get('levels') or []

@analysis_record_grouping.field('studyId')
async def resolve_record_grouping_study(record_grouping: dict, info):
    """Groupings are resolved live; null if the grouping is not readable or no longer exists."""
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    grouping_id = int(record_grouping['grouping_id'])
    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(grouping_id=grouping_id)
        if program is None:
            return None
        study = program.get_study(grouping_id=grouping_id)
        return study.id if study is not None else None

@analysis_group.field('recordGroups')
def resolve_group_record_groups(group: dict, info):
    return group.get('record_groups') or []
