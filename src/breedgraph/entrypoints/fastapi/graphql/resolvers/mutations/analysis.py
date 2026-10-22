from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.entrypoints.fastapi.graphql.licences import licences_not_accepted
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import get_context_views, get_context_lock
from breedgraph.domain.commands.analysis import RequestAnalysis
from breedgraph.domain.model.analysis import AnalysisConfigInvalid, AnalysisMessage, AnalysisErrorCode


import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("analysisSubmit")
@graphql_payload
@require_authentication
async def submit_analysis(
        _,
        info,
        analysis: dict
) -> str:
    user_id: int = info.context.get('user_id')
    logger.debug(f"User {user_id} requesting analysis {analysis}")
    await _require_licences_accepted(info, analysis.get('dataset_ids') or [])
    bus = info.context.get('bus')
    return await bus.handle(RequestAnalysis(agent_id=user_id, analysis=analysis))


async def _require_licences_accepted(info, dataset_ids: list) -> None:
    """
    An analysis reads its datasets' records, so it needs their studies' licences accepted, as the records do
    (docs/licences.md §5). Checked as it is submitted, while the request's acceptances are there; it runs later.
    """
    try:
        dataset_ids = [int(dataset_id) for dataset_id in dataset_ids]
    except (TypeError, ValueError):
        return  # left to the analysis's own validation
    if not dataset_ids:
        return
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        datasets = {dataset.id: dataset for dataset in await views.datasets.get_datasets(dataset_ids=dataset_ids)}
    required = {
        index: datasets[dataset_id] for index, dataset_id in enumerate(dataset_ids)
        if dataset_id in datasets and not datasets[dataset_id].redacted and datasets[dataset_id].licence_required
    }
    missing = set(await licences_not_accepted(info.context, [dataset.licence for dataset in required.values()]))
    errors = [
        AnalysisMessage(
            code=AnalysisErrorCode.LICENCE_NOT_ACCEPTED,
            message=f"Dataset {dataset.id} needs its study's licence, reference {dataset.licence}, accepted",
            path=['datasetIds', str(index)]
        )
        for index, dataset in required.items() if dataset.licence in missing
    ]
    if errors:
        raise AnalysisConfigInvalid(errors)

@graphql_mutation.field("analysisDelete")
@graphql_payload
@require_authentication
async def delete_analysis(
        _,
        info,
        id: str
) -> bool:
    user_id: int = info.context.get('user_id')
    logger.debug(f"User {user_id} deleting analysis {id}")
    bus = info.context.get('bus')
    await bus.state_store.delete_analysis(agent_id=user_id, analysis_id=id)
    return True
