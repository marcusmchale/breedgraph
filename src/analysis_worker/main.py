import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from analysis_worker.service_layer.worker import AnalysisWorker
from analysis_worker.adapters.http.client import AnalysisAPIClient
from analysis_worker.config import (
    ANALYSIS_WORKER_AUTH_TOKEN, LOG_CONFIG, API_URL, ANALYSIS_POLL_INTERVAL
)

import logging.config

logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger(__name__)

logger.info("Starting Analysis Worker")

async def run_worker(api_url: str, poll_interval: int):
    """
    Run the worker loop.

    Jobs are leased, so several workers may run against the same web server.
    A job whose lease expires before its outcome is reported is re-queued.
    """
    logger.info(f"Starting Analysis Worker with config: api_url={api_url}, poll_interval={poll_interval}s")

    client = AnalysisAPIClient(base_url=api_url, auth_token=ANALYSIS_WORKER_AUTH_TOKEN)
    # a fresh process for each job: embedded R is not thread safe and keeps state between calls
    executor = ProcessPoolExecutor(
        max_workers=1, mp_context=multiprocessing.get_context('spawn'), max_tasks_per_child=1
    )
    worker = AnalysisWorker(client=client, poll_interval=poll_interval, executor=executor)

    try:
        await worker.run()
    except asyncio.CancelledError:
        logger.info("Worker interrupted, shutting down gracefully")
        await worker.shutdown()
    except Exception as e:
        logger.exception(f"Worker failed: {e}")
        raise
    finally:
        executor.shutdown(cancel_futures=True)
        await client.close()


def main():
    """Main entry point"""
    logger.info("Analysis Worker starting up")

    try:
        asyncio.run(run_worker(api_url=API_URL, poll_interval=ANALYSIS_POLL_INTERVAL))
        logger.info("Worker shutdown complete")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.critical(f"Failed to start worker: {e}")
        raise SystemExit(1)


if __name__ == '__main__':
    main()
