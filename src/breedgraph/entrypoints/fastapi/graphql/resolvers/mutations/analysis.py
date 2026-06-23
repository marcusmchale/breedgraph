from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.analysis import RequestAnalysis


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
    key = await bus.state_store.store_analysis(agent_id=user_id, analysis=analysis)
    cmd = RequestAnalysis(agent_id=user_id, analysis_id=key)
    await bus.handle(cmd)
    return key
