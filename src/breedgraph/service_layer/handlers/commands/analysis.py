from asyncio import Queue

from breedgraph.domain import commands, events

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def request_analysis(
        cmd: commands.analysis.RequestAnalysis,
        event_queue: Queue
):
    event = events.analysis.AnalysisRequested(agent_id=cmd.agent_id, analysis_id=cmd.analysis_id)
    await event_queue.put(event)