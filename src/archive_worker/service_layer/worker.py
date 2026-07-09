import asyncio
import logging
from pathlib import Path

from archive_worker.adapters.http.abstract_client import AbstractArchiveAPIClient
from archive_worker.service_layer.handlers import (
    handle_archival,
    handle_retrieval,
    handle_deletion
)

logger = logging.getLogger(__name__)


class ArchiveWorker:
    """Main worker that polls for jobs and executes them"""

    def __init__(
            self,
            client: AbstractArchiveAPIClient,
            destination: Path,
            poll_interval: int|float = 5,
            resume: bool = True
    ):
        self.client = client
        self.destination = destination
        self.poll_interval = poll_interval
        self.destination.mkdir(parents=True, exist_ok=True)
        self.resume = resume
        self._shutdown_event = asyncio.Event()

    async def run(self):
        """Start the worker loop"""
        logger.info("Archive worker started")
        if self.resume:
            logger.debug("Resume interrupted processes")
            try:
                await self._process_archival(resume=True)
                await self._process_retrieval(resume=True)
                await self._process_deletion(resume=True)

            except Exception as e:
                logger.exception(f"Error in resuming: {e}")

        # Main polling loop
        logger.debug("Collect new processes")
        while not self._shutdown_event.is_set():
            try:
                await self._process_archival()
                await self._process_retrieval()
                await self._process_deletion()

                # Wait for poll interval or shutdown signal
                try:
                    logger.debug("Wait for shutdown")
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.poll_interval
                    )
                    # If we get here, shutdown was requested
                    break
                except asyncio.TimeoutError:
                    logger.debug("Shutdown not requested, continue")
                    # Normal timeout, continue loop
                    continue

            except Exception as e:
                logger.exception(f"Error in worker loop: {e}")
                # Still respect shutdown during error handling
                if not self._shutdown_event.is_set():
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self.poll_interval
                        )
                        break
                    except asyncio.TimeoutError:
                        continue

        logger.info("Archive worker shutdown complete")

    async def shutdown(self):
        """Gracefully shutdown the worker"""
        logger.info("Initiating worker shutdown...")
        self._shutdown_event.set()

    async def _process_archival(self, resume: bool = False):
        """Process files marked for archival or optionally resume files marked as archiving"""
        try:
            if resume:
                record = await self.client.get_archiving()
            else:
                record = await self.client.get_archival_pending()

            if record:
                logger.info(f"Processing archival for {record['file_id']}")
                await handle_archival(self.client, self.destination, record)
                await self._process_archival(resume=resume)

        except Exception as e:
            logger.error(f"Archival processing failed: {e}")

    async def _process_retrieval(self, resume: bool = False):
        """Process files marked for retrieval"""
        try:
            if resume:
                record = await self.client.get_retrieving()
            else:
                record = await self.client.get_retrieval_pending()

            if record:
                logger.info(f"Processing retrieval for {record['file_id']}")
                await handle_retrieval(self.client, self.destination, record)
                await self._process_retrieval(resume=resume)
        except Exception as e:
            logger.error(f"Retrieval processing failed: {e}")

    async def _process_deletion(self, resume: bool = False):
        """Process files marked for deletion"""
        try:
            if resume:
                record = await self.client.get_deleting()
            else:
                record = await self.client.get_deletion_pending()

            if record:
                logger.info(f"Processing deletion for {record['file_id']}")
                await handle_deletion(self.client, self.destination, record)
                await self._process_deletion(resume=resume)
        except Exception as e:
            logger.error(f"Deletion processing failed: {e}")