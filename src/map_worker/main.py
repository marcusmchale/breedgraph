import asyncio
import signal
from pathlib import Path

from map_worker.service_layer.worker import MapWorker
from map_worker.service_layer.handlers import MapHandlers
from map_worker.adapters.http.client import MapAPIClient
from map_worker.fetching import PmtilesCommand
from map_worker.config import (
    MAP_WORKER_AUTH_TOKEN, LOG_CONFIG, API_URL, MAP_POLL_INTERVAL, MAP_WORK_PATH, MAP_PMTILES_COMMAND,
    GEOBOUNDARIES_URL, PROTOMAPS_BUILDS_URL
)

import logging.config

logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger(__name__)


async def run_worker(api_url: str, poll_interval: int):
    """
    Run the worker loop. Jobs it was doing when it last stopped are queued again by the API once their leases expire,
    so it starts with an empty work directory.
    """
    logger.info(f"Starting Map Worker with config: api_url={api_url}, work_path={MAP_WORK_PATH}, poll_interval={poll_interval}s")
    pmtiles = PmtilesCommand(MAP_PMTILES_COMMAND)
    if not pmtiles.available():
        raise RuntimeError(f"The pmtiles command ({MAP_PMTILES_COMMAND}) is not installed (breedgraph README.md, Maps)")
    handlers = MapHandlers(pmtiles, Path(MAP_WORK_PATH), GEOBOUNDARIES_URL, PROTOMAPS_BUILDS_URL)
    handlers.clear()
    client = MapAPIClient(base_url=api_url, auth_token=MAP_WORKER_AUTH_TOKEN)
    worker = MapWorker(client=client, handlers=handlers, poll_interval=poll_interval)
    # systemd stops the worker with SIGTERM: a running pmtiles is stopped with it
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, lambda: asyncio.ensure_future(worker.shutdown()))
    try:
        await worker.run()
    finally:
        await client.close()


def main():
    """Main entry point"""
    logger.info("Map Worker starting up")

    try:
        asyncio.run(run_worker(api_url=API_URL, poll_interval=MAP_POLL_INTERVAL))
        logger.info("Worker shutdown complete")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.critical(f"Failed to start worker: {e}")
        raise SystemExit(1)


if __name__ == '__main__':
    main()
