import asyncio
import logging
from concurrent.futures import Executor

from analysis_worker.adapters.http.abstract_client import AbstractAnalysisAPIClient
from analysis_worker.domain.model.job import AnalysisJob, AnalysisJobFailed, Message, ErrorCode
from analysis_worker.service_layer.runner import run_job

logger = logging.getLogger(__name__)


class AnalysisWorker:
    """Polls the web server for analysis jobs, runs them and reports the outcome"""

    def __init__(
            self,
            client: AbstractAnalysisAPIClient,
            poll_interval: int | float = 5,
            executor: Executor | None = None
    ):
        """
        :param executor: runs analyses; a process pool keeps embedded R on the main thread of a process.
            Defaults to a thread, which suits analyses not using R.
        """
        self.client = client
        self.poll_interval = poll_interval
        self.executor = executor
        self._shutdown_event = asyncio.Event()

    async def run(self):
        """Start the worker loop"""
        logger.info("Analysis worker started")
        while not self._shutdown_event.is_set():
            try:
                # process jobs until the queue is empty
                while not self._shutdown_event.is_set() and await self.process_next():
                    pass
            except Exception as e:
                logger.exception(f"Error in worker loop: {e}")

            # Wait for poll interval or shutdown signal
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.poll_interval)
                break
            except asyncio.TimeoutError:
                continue

        logger.info("Analysis worker shutdown complete")

    async def shutdown(self):
        """Gracefully shutdown the worker"""
        logger.info("Initiating worker shutdown...")
        self._shutdown_event.set()

    async def process_next(self) -> bool:
        """Lease, run and report the next job. Returns False if no job was queued."""
        job = await self.client.lease_job()
        if job is None:
            return False
        logger.info(f"Processing {job.analysis_type} analysis {job.analysis_id}")
        await self.process(job)
        return True

    async def process(self, job: AnalysisJob):
        try:
            # analyses are CPU bound, keep the event loop free
            if self.executor is None:
                outcome = await asyncio.to_thread(run_job, job)
            else:
                outcome = await asyncio.get_running_loop().run_in_executor(self.executor, run_job, job)
        except AnalysisJobFailed as e:
            logger.info(f"Analysis {job.analysis_id} failed: {e}")
            await self.client.post_failure(job, errors=e.errors, warnings=e.warnings)
            return
        except Exception as e:
            logger.exception(f"Analysis {job.analysis_id} raised an unexpected error: {e}")
            await self.client.post_failure(job, errors=[Message(
                code=ErrorCode.INTERNAL_ERROR, message="An internal error occurred while running the analysis"
            )], warnings=[])
            return
        await self.client.post_result(job, result=outcome.result, warnings=outcome.warnings)
