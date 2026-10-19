"""
Detailed map tiles for regions (service_layer/infrastructure/map_regions.py, README.md, Maps).

A country is fetched whole when it is added, unless its file would be larger than config.MAP_REGION_MAX_GB. Such a
country is divided: when a location in it is placed on the map, the section holding it is fetched, an ADM1 unit (a
state or province) or, when that is too large too, the ADM2 unit. Each region is cut from a Protomaps build by
pmtiles extract, at the zooms above the world file's, into MAP_TILES_PATH/regions/<key>.pmtiles with a <key>.json
sidecar, and tiles.json is rebuilt.

Requests only record who asked and start a task, so the event handlers stay free. In the state store (Redis), a lock
per region keeps processes from fetching the same one, its requestors are emailed when its fetch starts and ends, and
the pending regions are resumed at start. A placement is recorded once its section is known, after the country is
sized, so one interrupted before then is fetched only by scripts/map_tiles.py --regions.
"""
import asyncio
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Dict, Iterable, List, Set, Tuple

from breedgraph import config
from breedgraph.domain.events import Event
from breedgraph.domain.events.location_trees import (
    MapRegionFetching, MapCountryDivided, MapRegionReady, MapRegionFailed
)
from breedgraph.service_layer.infrastructure.map_regions import AbstractMapRegions
from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore

from .boundaries import GeoBoundaries
from .command import PmtilesCommand, ProtomapsBuilds, MapRegionError
from .regions import (
    Region, Point, COUNTRY, SECTION_LEVELS, REGIONS_DIRECTORY, WORLD_JSON,
    section_for, features_bounds, region_file, read_json, write_json, write_tiles_json
)

import logging
logger = logging.getLogger(__name__)

MAX_ZOOM = 15
LOCK_SECONDS = 60
POLL_SECONDS = 5
SIZE_WAIT_SECONDS = 600  # how long a placement waits for its country to be sized
SPACE_MARGIN = 0.1  # free space needed beyond a region's size, as a share of it
SPACE_RESERVE = 10 ** 9  # and in bytes


class Outcome(Enum):
    READY = 'ready'
    DIVIDED = 'divided'
    FAILED = 'failed'
    REMOVED = 'removed'  # the country was removed while its region was fetched
    ELSEWHERE = 'elsewhere'  # another process finished the region


class RegionRemoved(Exception):
    pass


class PmtilesMapRegions(AbstractMapRegions):

    def __init__(
            self,
            state_store: AbstractStateStore,
            publish: Callable[[Event], Awaitable[None]] | None = None,
            command: str | None = None,
            tiles_path: str | Path | None = None,
            boundaries_path: str | Path | None = None,
            max_gb: float | None = None,
            build: str | None = None,
            poll_seconds: float = POLL_SECONDS
    ):
        """publish puts the events that email requestors; without it, as for scripts/map_tiles.py, none are sent"""
        self.state_store = state_store
        self.publish = publish
        self.pmtiles = PmtilesCommand(config.MAP_PMTILES_COMMAND if command is None else command)
        self.tiles_path = Path(config.MAP_TILES_PATH if tiles_path is None else tiles_path)
        self.boundaries = GeoBoundaries(
            Path(config.MAP_BOUNDARIES_PATH if boundaries_path is None else boundaries_path)
        )
        self.max_bytes = (config.MAP_REGION_MAX_GB if max_gb is None else max_gb) * 10 ** 9
        self.builds = ProtomapsBuilds(config.MAP_TILES_BUILD if build is None else build)
        self.poll_seconds = poll_seconds
        self.enabled = False
        self._regions: Dict[str, asyncio.Task] = {}
        self._tasks: Set[asyncio.Task] = set()
        self._extracting = asyncio.Semaphore(1)  # one extract at a time in each process

    async def start(self) -> None:
        if not self.pmtiles.available():
            if self.pmtiles.command:
                logger.warning(
                    f"Detailed maps are not fetched: the pmtiles command ({self.pmtiles.command}) is not installed "
                    f"(README.md, Maps)"
                )
            else:
                logger.info("Detailed maps are not fetched: MAP_PMTILES_COMMAND is empty")
            return
        self.enabled = True
        for key in await self.state_store.get_pending_map_regions():
            try:
                region = Region.from_key(key)
            except ValueError:
                logger.warning(f"Dropping the request for an unknown map region: {key!r}")
                await self.state_store.finish_map_region(key)
                continue
            self._run_in_background(region)

    async def stop(self) -> None:
        self.enabled = False
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def wait_until_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def request_country(self, code: str, requested_by: int | None = None) -> None:
        if self.enabled:
            await self._request(Region(code), requested_by)

    async def request_places(
            self,
            code: str,
            coordinates: Iterable[Tuple[float, float]],
            requested_by: int | None = None
    ) -> None:
        points = [(latitude, longitude) for latitude, longitude in coordinates if None not in (latitude, longitude)]
        if self.enabled and points:
            self._spawn(self._place(Region(code), points, requested_by))

    async def remove_country(self, code: str) -> None:
        await self.state_store.remove_map_country(code)
        cancelled = [task for key, task in self._regions.items() if Region.from_key(key).code == code]
        for task in cancelled:
            task.cancel()
        await asyncio.gather(*cancelled, return_exceptions=True)
        removed = False
        for pattern in (f'{code}.*', f'{code}-*', f'.{code}.*', f'.{code}-*'):
            for path in (self.tiles_path / REGIONS_DIRECTORY).glob(pattern):
                path.unlink(missing_ok=True)
                removed = True
        for path in self.boundaries.path.glob(f'{code}-ADM?-*.geojson'):
            path.unlink(missing_ok=True)
        if removed:
            await asyncio.to_thread(write_tiles_json, self.tiles_path)
            logger.info(f"Removed the detailed maps for {code}")

    """ In the background """

    async def _request(self, region: Region, requested_by: int | None) -> None:
        """Record the request and start the fetch, telling a user who joins a fetch already under way"""
        if await self.state_store.add_map_region_request(region.key, requested_by):
            if await self.state_store.is_map_region_fetching(region.key):
                await self._notify_fetching(region, [requested_by])
        self._run_in_background(region)

    def _run_in_background(self, region: Region) -> None:
        running = self._regions.get(region.key)
        if running is None or running.done():
            task = self._spawn(self._fetch_while_pending(region))
            self._regions[region.key] = task
            task.add_done_callback(lambda done: self._forget(region.key, done))

    def _forget(self, key: str, task: asyncio.Task) -> None:
        if self._regions.get(key) is task:
            del self._regions[key]

    def _spawn(self, coroutine) -> asyncio.Task:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _fetch_while_pending(self, region: Region) -> None:
        """Fetch the region, again if it was requested once more as the fetch finished"""
        while True:
            try:
                await self.fetch(region)
                if not await self.state_store.is_map_region_pending(region.key):
                    return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"Fetching the detailed maps for {region.key} stopped")
                return

    async def _place(self, country: Region, points: List[Point], requested_by: int | None) -> None:
        """Fetch the sections holding the points, when the country is divided"""
        try:
            if region_file(self.tiles_path, country).exists():
                return
            size = await self._country_size(country, requested_by)
            if size is None:
                return  # the country could not be sized; whoever asked for it was told
            if size <= self.max_bytes:
                # the country's own fetch covers the points, unless it failed and should be tried again
                if not region_file(self.tiles_path, country).exists() \
                        and not await self.state_store.is_map_region_pending(country.key):
                    await self._request(country, requested_by)
                return
            for section, size in await self.sections(country.code, points):
                if size > self.max_bytes:
                    logger.error(f"Detailed maps for {section.key} could not be fetched: {size} bytes is too large")
                    await self._publish(MapRegionFailed, section, [requested_by])
                elif not region_file(self.tiles_path, section).exists():
                    await self._request(section, requested_by)
        except MapRegionError as e:
            logger.error(f"Detailed maps for locations in {country.code} could not be fetched: {e}")
            await self._publish(MapRegionFailed, country, [requested_by])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(f"Finding the detailed maps for locations in {country.code} stopped")

    async def _country_size(self, country: Region, requested_by: int | None) -> int | None:
        """The country's size, waiting while it is sized, after requesting it if it never was (as for a country
        added before maps were fetched)"""
        size = await self.state_store.get_map_region_size(country.key)
        if size is None and not await self.state_store.is_map_region_pending(country.key):
            await self._request(country, requested_by)
        waited = 0.0
        while size is None and waited < SIZE_WAIT_SECONDS and await self.state_store.is_map_region_pending(country.key):
            await asyncio.sleep(self.poll_seconds)
            waited += self.poll_seconds
            size = await self.state_store.get_map_region_size(country.key)
        return size

    """ In the foreground, as for scripts/map_tiles.py, or for the tasks above """

    async def fetch_now(self, region: Region, refresh: bool = False) -> Outcome:
        """Request the region and fetch it, or with refresh fetch it again from the newest build"""
        await self.state_store.add_map_region_request(region.key, None)
        return await self.fetch(region, refresh=refresh)

    async def fetch(self, region: Region, refresh: bool = False) -> Outcome:
        """
        Fetch a region requested, or divide a country too large, and tell its requestors. While another process
        works on the region this waits, and if that process finishes it (or the country is removed), returns ELSEWHERE.
        """
        async with self._holding(region) as held:
            if not held or not await self.state_store.is_map_region_pending(region.key):
                return Outcome.ELSEWHERE
            try:
                outcome = await self._fetch(region, refresh)
            except RegionRemoved:
                return Outcome.REMOVED
            except MapRegionError as e:
                logger.error(f"Detailed maps for {region.key} could not be fetched: {e}")
                outcome = Outcome.FAILED
            except Exception:
                logger.exception(f"Detailed maps for {region.key} could not be fetched")
                outcome = Outcome.FAILED
            users = await self.state_store.finish_map_region(region.key)
            event = {
                Outcome.READY: MapRegionReady, Outcome.DIVIDED: MapCountryDivided, Outcome.FAILED: MapRegionFailed
            }[outcome]
            await self._publish(event, region, users)
            return outcome

    async def _fetch(self, region: Region, refresh: bool) -> Outcome:
        file = region_file(self.tiles_path, region)
        if file.exists() and not refresh:
            return Outcome.READY
        size = await self.size(region, fresh=refresh)
        if region.level == COUNTRY and size > self.max_bytes and not file.exists():
            logger.info(f"Detailed maps for {region.key} would take {size} bytes, so it is divided")
            return Outcome.DIVIDED
        await self._extract(region, size)
        return Outcome.READY

    async def size(self, region: Region, fresh: bool = False) -> int:
        """The size in bytes of the region's file, from a dry run (kept, unless fresh)"""
        if not fresh:
            size = await self.state_store.get_map_region_size(region.key)
            if size is not None:
                return size
        world, build, _ = await self._build()
        outline, _ = await self.boundaries.outline(region)
        size = await self.pmtiles.size(build, outline, world['maxZoom'] + 1, MAX_ZOOM)
        await self.state_store.set_map_region_size(region.key, size)
        return size

    async def sections(self, code: str, points: Iterable[Point]) -> List[Tuple[Region, int]]:
        """
        The sections holding the points, with their sizes: for each point the ADM1 unit holding it, or when that is
        too large, the ADM2 unit (which is returned even when it is too large too)
        """
        found: Dict[Region, int] = {}
        features: Dict[str, List[dict]] = {}
        for point in points:
            for level in SECTION_LEVELS:
                if level not in features:
                    features[level] = await self.boundaries.features(code, level)
                feature = await asyncio.to_thread(section_for, features[level], point)
                if feature is None:
                    logger.info(f"A location in {code} lies far from every {level} outline, so has no section")
                    break
                try:
                    section = Region(code, level, (feature.get('properties') or {}).get('shapeID'))
                except ValueError as e:
                    raise MapRegionError(str(e))
                self.boundaries.save_section(section, feature)
                size = found.get(section) or await self.size(section)
                if size <= self.max_bytes or level == SECTION_LEVELS[-1]:
                    found[section] = size
                    break
        return list(found.items())

    async def _build(self) -> Tuple[dict, str, str | None]:
        """The world file's description, and the build to cut regions from, with its version"""
        world = read_json(self.tiles_path / WORLD_JSON)
        if world is None:
            raise MapRegionError(f"There is no world file in {self.tiles_path}: cut it first with scripts/map_tiles.py")
        version = world.get('version')
        build, version = await self.builds.latest(major=version.split('.')[0] if version else None)
        return world, build, version

    async def _extract(self, region: Region, size: int) -> None:
        world, build, version = await self._build()
        outline, features = await self.boundaries.outline(region)
        directory = self.tiles_path / REGIONS_DIRECTORY
        directory.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(directory).free
        if free < size * (1 + SPACE_MARGIN) + SPACE_RESERVE:
            raise MapRegionError(f"Not enough disk space: {size} bytes needed and {free} free")
        await self.state_store.set_map_region_fetching(region.key)
        await self._notify_fetching(region, await self.state_store.get_map_region_requestors(region.key))
        partial = directory / f'.{region.key}.pmtiles.partial'
        minzoom = world['maxZoom'] + 1
        logger.info(f"Fetching detailed maps for {region.key} ({size} bytes) from {build}")
        async with self._extracting:
            await self.pmtiles.extract(build, outline, partial, minzoom, MAX_ZOOM)
        if not await self.state_store.is_map_region_pending(region.key):
            partial.unlink(missing_ok=True)
            raise RegionRemoved(region.key)
        file = region_file(self.tiles_path, region)
        os.replace(partial, file)
        write_json(region_file(self.tiles_path, region, '.json'), {
            'key': region.key,
            'url': f'{REGIONS_DIRECTORY}/{file.name}',
            'name': await self._name(region, features),
            'country': region.code,
            'level': region.level,
            'shapeID': region.shape_id,
            'bounds': features_bounds(features),
            'minZoom': minzoom,
            'maxZoom': MAX_ZOOM,
            'build': build,
            'version': version,
            'size': file.stat().st_size,
            'updated': datetime.now(timezone.utc).isoformat(timespec='seconds')
        })
        await asyncio.to_thread(write_tiles_json, self.tiles_path)
        logger.info(f"Fetched detailed maps for {region.key}")

    @asynccontextmanager
    async def _holding(self, region: Region):
        """
        Hold the region's lock, yielding True. While another process holds it, wait; if that process finishes the
        region meanwhile, yield False.
        """
        token = await self.state_store.acquire_map_region_lock(region.key, LOCK_SECONDS)
        while token is None and await self.state_store.is_map_region_pending(region.key):
            await asyncio.sleep(self.poll_seconds)
            token = await self.state_store.acquire_map_region_lock(region.key, LOCK_SECONDS)
        if token is None:
            yield False
            return
        keeping = asyncio.create_task(self._keep_lock(region.key, token))
        try:
            yield True
        finally:
            keeping.cancel()
            await self.state_store.release_map_region_lock(region.key, token)

    async def _keep_lock(self, key: str, token: str) -> None:
        while True:
            await asyncio.sleep(LOCK_SECONDS / 3)
            if not await self.state_store.refresh_map_region_lock(key, token, LOCK_SECONDS):
                logger.warning(f"Lost the lock on the map region {key}, so another process may fetch it too")
                return

    """ Telling requestors """

    async def _notify_fetching(self, region: Region, users: List[int]) -> None:
        users = [user for user in users if await self.state_store.mark_map_region_notified(region.key, user)]
        await self._publish(MapRegionFetching, region, users)

    async def _publish(self, event: type, region: Region, users: List[int | None]) -> None:
        users = [user for user in users if user is not None]
        if self.publish is not None and users:
            await self.publish(event(name=await self._name(region), user_ids=users))

    async def _name(self, region: Region, features: List[dict] | None = None) -> str:
        """The country's name as BreedGraph has it, or a section's with its country's"""
        country = await self.state_store.get_country(region.code)
        name = country.name if country is not None else region.code
        if region.shape_id is None:
            return name
        sidecar = read_json(region_file(self.tiles_path, region, '.json'))
        if sidecar is not None:
            return sidecar['name']
        try:
            if features is None:
                _, features = await self.boundaries.outline(region)
            section = (features[0].get('properties') or {}).get('shapeName')
        except MapRegionError:
            section = None
        return f"{section or region.key} ({name})"
