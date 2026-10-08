from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.analysis import RequestAnalysis


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
    bus = info.context.get('bus')
    return await bus.handle(RequestAnalysis(agent_id=user_id, analysis=analysis))

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
