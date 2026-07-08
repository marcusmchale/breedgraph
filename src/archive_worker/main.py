import asyncio
from pathlib import Path

from archive_worker.service_layer.worker import ArchiveWorker
from archive_worker.adapters.http.client import ArchiveAPIClient
from archive_worker.config import (
    ARCHIVE_AUTH_TOKEN, LOG_CONFIG, API_URL, ARCHIVE_DESTINATION, ARCHIVE_POLL_INTERVAL
)

import logging.config

logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger(__name__)


async def run_worker(api_url: str, destination: str, poll_interval: int, resume: bool = True):
    """
    Run the worker loop.

    Only one worker should be run with resume=True.
    On startup it will first resume any interrupted archiving, retrieving and deleting
    before fetching any new records.
    """
    logger.info(
        f"Starting Archive Worker with config: api_url={api_url}, destination={destination}, poll_interval={poll_interval}s, resume={resume}")

    client = ArchiveAPIClient(base_url=api_url, auth_token=ARCHIVE_AUTH_TOKEN)
    worker = ArchiveWorker(
        client=client,
        destination=Path(destination),
        poll_interval=poll_interval,
        resume=resume
    )

    try:
        await worker.run()
    except asyncio.CancelledError:
        logger.info("Worker interrupted, shutting down gracefully")
        await worker.shutdown()
    except Exception as e:
        logger.exception(f"Worker failed: {e}")
        raise


def main():
    """Main entry point"""
    logger.info("Archive Worker starting up")

    try:
        asyncio.run(run_worker(
            api_url=API_URL,
            destination=ARCHIVE_DESTINATION,
            poll_interval=ARCHIVE_POLL_INTERVAL,
            resume=True
        ))
        logger.info("Worker shutdown complete")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.critical(f"Failed to start worker: {e}")
        raise SystemExit(1)


if __name__ == '__main__':
    main()