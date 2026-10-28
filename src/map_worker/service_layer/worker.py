import asyncio
import logging
import time
from typing import Set

import httpx

from map_worker.adapters.http.abstract_client import AbstractMapAPIClient, UploadRefused
from map_worker.domain.job import MapJob, Extract, BadJob, LANES, check
from map_worker.fetching import MapRegionError
from map_worker.service_layer.handlers import MapHandlers

logger = logging.getLogger(__name__)

UPLOAD_ATTEMPTS = 5
UPLOAD_RETRY_SECONDS = 30
# while the API can't be asked for jobs, as while its site restarts or resets, how often a lane says it still can't
UNANSWERED_REPEAT_SECONDS = 3600


def duration(seconds: float) -> str:
    minutes, seconds = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return ' '.join(f"{n} {unit}" for n, unit in ((hours, 'h'), (minutes, 'min'), (seconds, 's')) if n) or '0 s'


class Unanswered:
    """
    A lane's polls the API has not answered: said when the first fails, every UNANSWERED_REPEAT_SECONDS while they go
    on, and when one is answered again, rather than at each poll
    """

    def __init__(self, lane: str, poll_interval: float, clock=time.monotonic):
        self.lane = lane
        self.poll_interval = poll_interval
        self.clock = clock
        self.since: float | None = None
        self.said: float = 0
        self.polls = 0

    def failed(self, error: Exception):
        now = self.clock()
        self.polls += 1
        reason = f"{type(error).__name__}: {error}"
        if self.since is None:
            self.since = self.said = now
            logger.warning(
                f"The API could not be asked for {self.lane} jobs: {reason}. Asking every {self.poll_interval:g} s, "
                f"and saying when it answers"
            )
        elif now - self.said >= UNANSWERED_REPEAT_SECONDS:
            self.said = now
            logger.warning(
                f"The API has not answered for {self.lane} jobs for {duration(now - self.since)} ({self.polls} polls): "
                f"{reason}"
            )

    def answered(self):
        if self.since is not None:
            logger.info(
                f"The API answers for {self.lane} jobs again, after {duration(self.clock() - self.since)} "
                f"({self.polls} polls unanswered)"
            )
            self.since, self.polls = None, 0


class MapWorker:
    """
    Polls the web server for map jobs, one lane at a time each (an extract never holds up a quick job), does them and
    reports the outcome. While a job runs its lease is renewed; when the API refuses a renewal, the job was cancelled
    (its country removed) or went to another, and the job is stopped.
    """

    def __init__(self, client: AbstractMapAPIClient, handlers: MapHandlers, poll_interval: float = 5):
        self.client = client
        self.handlers = handlers
        self.poll_interval = poll_interval
        self.upload_retry_seconds = UPLOAD_RETRY_SECONDS
        self._shutdown_event = asyncio.Event()
        self._running: Set[asyncio.Task] = set()

    async def run(self):
        logger.info("Map worker started")
        await asyncio.gather(*(self._run_lane(lane) for lane in LANES))
        logger.info("Map worker shutdown complete")

    async def _run_lane(self, lane: str):
        unanswered = Unanswered(lane, self.poll_interval)
        while not self._shutdown_event.is_set():
            try:
                # process jobs until the lane is empty
                while not self._shutdown_event.is_set() and await self.process_next(lane):
                    pass
                unanswered.answered()
            except httpx.HTTPError as e:
                # as while the API restarts: a line when it stops answering and when it answers again, not a traceback
                unanswered.failed(e)
            except Exception as e:
                logger.exception(f"Error in the {lane} lane: {e}")

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.poll_interval)
                break
            except asyncio.TimeoutError:
                continue

    async def shutdown(self):
        """Stop, leaving the jobs under way to be queued again when their leases expire"""
        logger.info("Initiating worker shutdown...")
        self._shutdown_event.set()
        for task in list(self._running):
            task.cancel()

    async def process_next(self, lane: str) -> bool:
        """Lease, do and report the next job of the lane. Returns False if none was queued."""
        job = await self.client.lease(lane)
        if job is None:
            return False
        work = asyncio.create_task(self.process(job))
        self._running.add(work)
        renewing = asyncio.create_task(self._keep_lease(job, work))
        try:
            await work
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise  # the lane itself was cancelled, not just the job
            if not self._shutdown_event.is_set():
                logger.info(f"Stopped the {job.kind} job for {job.key}: it is no longer leased to this worker")
        finally:
            self._running.discard(work)
            renewing.cancel()
        return True

    async def _keep_lease(self, job: MapJob, work: asyncio.Task):
        while True:
            await asyncio.sleep(job.lease_seconds / 3)
            try:
                held = await self.client.renew(job)
            except httpx.HTTPError as e:
                logger.warning(f"Could not renew the lease on the {job.kind} job for {job.key}: {e}")
                continue
            if not held:
                work.cancel()
                return

    async def process(self, job: MapJob):
        logger.info(f"Doing the {job.kind} job for {job.key}")
        try:
            check(job)
            outcome = await self.handlers.handle(job)
        except BadJob as e:
            logger.error(f"Refused the {job.kind} job for {job.key}: {e}")
            await self.client.post_failure(job, f"The map worker refused the job: {e}")
            return
        except MapRegionError as e:
            logger.error(f"The {job.kind} job for {job.key} failed: {e}")
            await self.client.post_failure(job, str(e))
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"The {job.kind} job for {job.key} raised an unexpected error: {e}")
            await self.client.post_failure(job, "An internal error occurred in the map worker")
            return
        if isinstance(outcome, Extract):
            try:
                await self._upload(job, outcome)
            finally:
                if outcome.temporary:
                    outcome.path.unlink(missing_ok=True)
        else:
            await self.client.post_result(job, outcome)
        logger.info(f"Done the {job.kind} job for {job.key}")

    async def _upload(self, job: MapJob, extract: Extract):
        """Send the file, again after a break in the connection unless the job was cancelled meanwhile"""
        for attempt in range(1, UPLOAD_ATTEMPTS + 1):
            try:
                await self.client.upload(job, extract)
                return
            except UploadRefused as e:
                logger.error(f"The API refused the extract of {job.key}: {e}")
                await self.client.post_failure(job, f"The API refused the file: {e}")
                return
            except httpx.HTTPError as e:
                logger.warning(f"Sending the extract of {job.key} failed (attempt {attempt}): {e}")
            await asyncio.sleep(self.upload_retry_seconds)
            try:
                if not await self.client.renew(job):
                    return
            except httpx.HTTPError:
                pass
        await self.client.post_failure(job, f"The file could not be sent in {UPLOAD_ATTEMPTS} attempts")
