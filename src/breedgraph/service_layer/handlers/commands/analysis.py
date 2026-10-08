from asyncio import Queue

from pydantic import ValidationError

from breedgraph.domain import commands, events
from breedgraph.domain.importers.analysis import AnalysisInputImport, validation_messages
from breedgraph.domain.model.analysis import AnalysisConfigInvalid
from breedgraph.domain.services.analysis_validation import validate_request
from breedgraph.service_layer.infrastructure import AbstractStateStore

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def request_analysis(
        cmd: commands.analysis.RequestAnalysis,
        state_store: AbstractStateStore,
        event_queue: Queue
) -> str:
    """
    Validate the analysis configuration before storing it, so invalid input is rejected immediately.
    Returns the analysis ID.
    """
    try:
        request = AnalysisInputImport(**cmd.analysis).to_domain()
    except ValidationError as e:
        raise AnalysisConfigInvalid(validation_messages(e))

    errors = validate_request(request)
    if errors:
        raise AnalysisConfigInvalid(errors)

    analysis_id = await state_store.store_analysis(agent_id=cmd.agent_id, analysis=cmd.analysis)
    await event_queue.put(events.analysis.AnalysisRequested(agent_id=cmd.agent_id, analysis_id=analysis_id))
    return analysis_id
