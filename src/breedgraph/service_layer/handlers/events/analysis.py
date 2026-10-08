from breedgraph.domain import events
from breedgraph.service_layer.infrastructure import AbstractStateStore, AbstractUnitOfWorkFactory
from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

from breedgraph.domain.importers.analysis import AnalysisInputImport
from breedgraph.domain.model.analysis import AnalysisMessage, AnalysisFailed, AnalysisErrorCode
from breedgraph.domain.model.submissions import SubmissionStatus
from breedgraph.domain.services.analysis_job import build_job_payload
from breedgraph.domain.services.analysis_preparation import prepare_observations
from breedgraph.service_layer.application.analysis_context import AnalysisContextLoader


@handlers.event_handler()
async def analysis_requested(
        event: events.analysis.AnalysisRequested,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    """
    Prepare the observations of an analysis and queue the job for the analysis worker.
    Data access and access control stay here; the worker only receives the job payload.
    Messages are written once, when the job fails or when the worker reports.
    """
    analysis_id = event.analysis_id
    await state_store.reset_analysis_messages(analysis_id)
    await state_store.set_analysis_status(analysis_id, SubmissionStatus.PROCESSING)
    warnings: list[AnalysisMessage] = []
    try:
        stored = await state_store.get_analysis_config(agent_id=event.agent_id, analysis_id=analysis_id)
        # validated when requested
        request = AnalysisInputImport(**stored).to_domain()
        async with uow_factory.get_uow(user_id=event.agent_id) as uow:
            context = await AnalysisContextLoader(uow, user_id=event.agent_id, warnings=warnings).load(request)
        frame = prepare_observations(context, warnings)
        payload = build_job_payload(analysis_id, request, frame)
    except AnalysisFailed as e:
        await state_store.fail_analysis(
            analysis_id,
            errors=[m.model_dump() for m in e.errors],
            warnings=[w.model_dump() for w in warnings]
        )
        return
    except Exception as e:
        logger.exception(f"Failed to prepare analysis {analysis_id}: {e}")
        await state_store.fail_analysis(
            analysis_id,
            errors=[AnalysisMessage(
                code=AnalysisErrorCode.INTERNAL_ERROR, message="An internal error occurred while preparing the analysis"
            ).model_dump()],
            warnings=[w.model_dump() for w in warnings]
        )
        return

    await state_store.enqueue_analysis_job(analysis_id, payload, warnings=[w.model_dump() for w in warnings])
