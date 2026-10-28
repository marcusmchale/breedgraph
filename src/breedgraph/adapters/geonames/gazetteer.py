"""
The place search's names (service_layer/infrastructure/gazetteer.py, docs/maps.md), from GeoNames.

A country's places are fetched when it is added, the world's towns when the API first starts, and both at any start
for countries in the location trees whose places were never fetched or failed. Each key (a country's alpha-3 code, or
'world') is one gzipped file, written by map_worker.fetching.write_gazetteer, kept in GAZETTEER_PATH/places and loaded
into the database beside it (index.py), so that the database can be made again from them when its schema changes.

Requests only record the key and start a task, so the event handlers stay free. In the state store (Redis), a lock per
key keeps processes from fetching the same one, the pending keys are resumed at start, and why a fetch failed is kept
for the location map. The files are downloaded by the API itself from config.GEONAMES_URL, or with config.MAP_WORKER
by the map worker, whose cache sends a file again rather than downloading it while it is recent.

Searches run in threads, a few at a time, each within index.SEARCH_SECONDS; what is searched for is never logged.
"""
import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Set

from breedgraph import config
from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.location_trees import LocationOutput
from breedgraph.service_layer.infrastructure.gazetteer import AbstractGazetteer, Place, PlacesStatus
from breedgraph.service_layer.infrastructure.map_regions import MapState
from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from breedgraph.adapters.pmtiles.command import MapRegionError
from breedgraph.adapters.pmtiles.jobs import MapJobs, sweep_uploads
from breedgraph.adapters.pmtiles.map_regions import FAILED_UNKNOWN
from map_worker.fetching import download_gazetteer

from .countries import read_countries
from .index import GazetteerIndex, GazetteerFileError, SearchTooLong, DATABASE, PLACES_DIRECTORY, WORLD

import logging
logger = logging.getLogger(__name__)

LOCK_SECONDS = 60
POLL_SECONDS = 5
SEARCHES_AT_ONCE = 4  # in each process; the rest wait their turn
SEARCH_WAIT_SECONDS = 5  # and are refused when it doesn't come
NOT_AVAILABLE = "Place search is not available, please try again later"


class PlacesRemoved(Exception):
    """The country was removed while its places were fetched"""


class GeoNamesGazetteer(AbstractGazetteer):

    def __init__(
            self,
            state_store: AbstractStateStore,
            path: str | Path | None = None,
            worker: bool | None = None,
            geonames_url: str | None = None,
            poll_seconds: float = POLL_SECONDS
    ):
        """
        worker (config.MAP_WORKER) has the map worker fetch the files; else the API downloads them from geonames_url
        (config.GEONAMES_URL), and fetches none when it is empty
        """
        self.state_store = state_store
        self.path = Path(config.GAZETTEER_PATH if path is None else path)
        self.files = self.path / PLACES_DIRECTORY
        self.index = GazetteerIndex(self.path / DATABASE)
        self.worker = config.MAP_WORKER if worker is None else worker
        self.geonames_url = config.GEONAMES_URL if geonames_url is None else geonames_url
        self.jobs = MapJobs(state_store, poll_seconds)
        self.poll_seconds = poll_seconds
        self.ready = False  # whether the database is made, so searches are answered
        self.enabled = False  # whether places are fetched
        self._fetches: Dict[str, asyncio.Task] = {}
        self._tasks: Set[asyncio.Task] = set()
        self._searching = asyncio.Semaphore(SEARCHES_AT_ONCE)

    def file(self, key: str) -> Path:
        return self.files / f'{key}.tsv.gz'

    async def start(self) -> None:
        try:
            made = await asyncio.to_thread(self.index.create, read_countries().values())
        except (sqlite3.Error, OSError):
            logger.exception("The place search's database could not be made, so places cannot be searched")
            return
        self.ready = True
        self.files.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(sweep_uploads, self.files)
        if made:
            self._spawn(self._load_kept())
        if self.worker:
            logger.info("Places for the place search are fetched by the map worker")
            if not config.MAP_WORKER_AUTH_TOKEN:
                logger.warning("MAP_WORKER is set but MAP_WORKER_AUTH_TOKEN is empty, so no map worker can fetch them")
        elif not self.geonames_url:
            logger.info("Places for the place search are not fetched: GEONAMES_URL is empty")
            return
        self.enabled = True
        keys = set(await self.state_store.get_pending_gazetteer())
        if not self.file(WORLD).exists():
            keys.add(WORLD)
        async for country in self.state_store.get_countries():
            if isinstance(country, LocationOutput) and not self.file(country.code).exists():
                keys.add(country.code)
        for key in sorted(keys, key=lambda key: (key != WORLD, key)):
            await self._request(key)

    async def stop(self) -> None:
        self.enabled = False
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def wait_until_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def request_country(self, code: str) -> None:
        if self.enabled:
            await self._request(code)

    async def remove_country(self, code: str) -> None:
        await self.state_store.remove_gazetteer(code)
        await self.state_store.delete_map_job('gazetteer', code)
        fetching = self._fetches.get(code)
        if fetching is not None:
            fetching.cancel()
            await asyncio.gather(fetching, return_exceptions=True)
        for path in [self.file(code), *self.files.glob(f'.{code}.*')]:
            path.unlink(missing_ok=True)
        if self.ready:
            await self._in_thread(self.index.remove_country, code)
            logger.info(f"Removed the places of {code} from the place search")

    """ In the background """

    async def _request(self, key: str) -> None:
        await self.state_store.add_gazetteer_request(key)
        running = self._fetches.get(key)
        if running is None or running.done():
            task = self._spawn(self._fetch_while_pending(key))
            self._fetches[key] = task
            task.add_done_callback(lambda done: self._forget(key, done))

    def _forget(self, key: str, task: asyncio.Task) -> None:
        if self._fetches.get(key) is task:
            del self._fetches[key]

    def _spawn(self, coroutine) -> asyncio.Task:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _fetch_while_pending(self, key: str) -> None:
        """Fetch the key's places, again if they were requested once more as the fetch finished"""
        while True:
            try:
                await self.fetch(key)
                if not await self.state_store.is_gazetteer_pending(key):
                    return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"Fetching the places of {key} for the place search stopped")
                return

    async def _load_kept(self) -> None:
        """Load the database, made again, from the files kept: the world's, then the countries'"""
        for path in sorted(self.files.glob('*.tsv.gz'), key=lambda path: path.name != f'{WORLD}.tsv.gz'):
            key = path.name.removesuffix('.tsv.gz')
            try:
                await self._load(key)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"The places of {key} kept for the place search could not be loaded again")

    """ In the foreground, as for scripts/map_tiles.py, or for the tasks above """

    async def fetch_now(self, key: str, fresh: bool = False) -> bool:
        """Request the key's places and fetch them, or with fresh download them anew"""
        await self.state_store.add_gazetteer_request(key)
        return await self.fetch(key, fresh=fresh)

    async def fetch(self, key: str, fresh: bool = False) -> bool:
        """
        Fetch and load the places requested for the key, keeping why they failed if they do: whether they were
        loaded. While another process fetches them this waits, and returns False when it is done.
        """
        async with self._holding(key) as held:
            if not held or not await self.state_store.is_gazetteer_pending(key):
                return False
            error = None
            try:
                await self._fetch(key, fresh)
            except PlacesRemoved:
                return False
            except (MapRegionError, GazetteerFileError) as e:
                logger.error(f"The places of {key} for the place search could not be fetched: {e}")
                error = FAILED_UNKNOWN
            except Exception:
                logger.exception(f"The places of {key} for the place search could not be fetched")
                error = FAILED_UNKNOWN
            await self.state_store.finish_gazetteer(key, error=error)
            return error is None

    async def _fetch(self, key: str, fresh: bool) -> None:
        if fresh or not self.file(key).exists():
            await self._download(key, fresh)
        if not await self.state_store.is_gazetteer_pending(key):
            self.file(key).unlink(missing_ok=True)
            raise PlacesRemoved(key)
        await self._load(key)
        if key != WORLD and not await self.state_store.is_gazetteer_pending(key):
            # removed, by another process, as they were loaded
            self.file(key).unlink(missing_ok=True)
            await self._in_thread(self.index.remove_country, key)
            raise PlacesRemoved(key)

    async def _download(self, key: str, fresh: bool) -> None:
        code = None
        if key != WORLD:
            country = read_countries().get(key)
            if country is None:
                raise MapRegionError(f"{key} is not one of the countries")
            code = country.iso2
        if self.worker:
            payload = {'fresh': fresh} if code is None else {'code': code, 'fresh': fresh}
            await self.jobs.take_file('gazetteer', key, payload, self.file(key))
            return
        if not self.geonames_url:
            raise MapRegionError("GEONAMES_URL is empty")
        download = self.files / f'.{key}.download.tsv.gz'
        try:
            await download_gazetteer(self.geonames_url, key, code, download)
            os.replace(download, self.file(key))
        finally:
            download.unlink(missing_ok=True)

    async def _load(self, key: str) -> None:
        """The key's file into the database; a file that cannot be loaded is deleted, to be fetched anew"""
        try:
            if key == WORLD:
                await self._in_thread(self.index.load_world, self.file(key))
            else:
                await self._in_thread(self.index.load_country, key, self.file(key))
        except GazetteerFileError:
            self.file(key).unlink(missing_ok=True)
            raise

    @staticmethod
    async def _in_thread(function, *arguments):
        """
        Write to the database in a thread, which a cancellation waits for, so that a country removed as its places
        load is removed after they are
        """
        writing = asyncio.ensure_future(asyncio.to_thread(function, *arguments))
        try:
            return await asyncio.shield(writing)
        except asyncio.CancelledError:
            await asyncio.gather(writing, return_exceptions=True)
            raise

    @asynccontextmanager
    async def _holding(self, key: str):
        """
        Hold the key's lock, yielding True. While another process holds it, wait; if that process finishes the key
        meanwhile, yield False.
        """
        lock = f'gazetteer:{key}'  # beside the map regions' locks
        token = await self.state_store.acquire_map_region_lock(lock, LOCK_SECONDS)
        while token is None and await self.state_store.is_gazetteer_pending(key):
            await asyncio.sleep(self.poll_seconds)
            token = await self.state_store.acquire_map_region_lock(lock, LOCK_SECONDS)
        if token is None:
            yield False
            return
        keeping = asyncio.create_task(self._keep_lock(lock, token))
        try:
            yield True
        finally:
            keeping.cancel()
            await self.state_store.release_map_region_lock(lock, token)

    async def _keep_lock(self, lock: str, token: str) -> None:
        while True:
            await asyncio.sleep(LOCK_SECONDS / 3)
            if not await self.state_store.refresh_map_region_lock(lock, token, LOCK_SECONDS):
                logger.warning(f"Lost the lock on {lock}, so another process may fetch it too")
                return

    """ Searches, and where a country's places stand """

    async def search_places(
            self,
            query: str,
            viewbox: List[float] | None = None,
            bounded: bool = False,
            country: str | None = None,
            limit: int = 5
    ) -> List[Place]:
        if not self.ready:
            raise IllegalOperationError(NOT_AVAILABLE)
        try:
            await asyncio.wait_for(self._searching.acquire(), SEARCH_WAIT_SECONDS)
        except TimeoutError:
            logger.warning("A place search was refused: too many were under way")
            raise IllegalOperationError("Place search is busy, please try again in a moment")
        try:
            return await asyncio.to_thread(self.index.search, query, viewbox, bounded, country, limit)
        except SearchTooLong:
            raise IllegalOperationError("That search took too long: please type more of the name")
        except ValueError as e:
            raise IllegalOperationError(str(e))
        except (sqlite3.Error, OSError) as e:
            logger.error(f"A place search failed: {type(e).__name__}")
            raise IllegalOperationError(NOT_AVAILABLE)
        finally:
            self._searching.release()

    async def country_place(self, code: str) -> Place | None:
        if not self.ready:
            return None
        return await asyncio.to_thread(self.index.country_place, code)

    async def status(self, code: str) -> PlacesStatus:
        towns = self.ready and await asyncio.to_thread(self.index.world_loaded)
        if await self.state_store.is_gazetteer_pending(code):
            return PlacesStatus(MapState.PENDING, self.enabled, towns)
        if self.ready and code in await asyncio.to_thread(self.index.loaded):
            return PlacesStatus(MapState.READY, self.enabled, towns)
        error = (await self.state_store.get_gazetteer_failures()).get(code)
        if error is not None:
            return PlacesStatus(MapState.FAILED, self.enabled, towns, error)
        return PlacesStatus(MapState.NONE, self.enabled, towns)
