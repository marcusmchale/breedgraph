"""
The go-pmtiles command (docs/maps.md), which cuts regions out of a Protomaps build reading only the parts it needs,
and the choice of build. The command and the list of builds are in map_worker.fetching, which the map worker runs too.
"""
import time
from typing import List, Tuple

from breedgraph import config
from map_worker.fetching import MapRegionError, parse_archive_size, PmtilesCommand, latest_build, list_builds

__all__ = ['MapRegionError', 'parse_archive_size', 'PmtilesCommand', 'latest_build', 'ProtomapsBuilds']

BUILDS_CACHE_SECONDS = 3600


class ProtomapsBuilds:
    """The build to cut regions from: config.MAP_TILES_BUILD, or the newest of Protomaps' daily builds"""

    def __init__(self, build: str = 'latest'):
        self.build = build
        self._builds: List[dict] = []
        self._read_at = 0.0

    async def _fetch_list(self) -> List[dict]:
        return await list_builds(config.PROTOMAPS_BUILDS_URL)

    async def _list(self) -> List[dict]:
        if time.monotonic() - self._read_at > BUILDS_CACHE_SECONDS or not self._builds:
            self._builds = await self._fetch_list()
            self._read_at = time.monotonic()
        return self._builds

    async def latest(self, major: str | None = None) -> Tuple[str, str | None]:
        """The build's URL and its tiles' version (None for a pinned build)"""
        if self.build != 'latest':
            return self.build, None
        build = latest_build(await self._list(), major)
        if build is None:
            raise MapRegionError(
                f"No Protomaps build of version {major} is available: cut the world file again from a newer build "
                f"(scripts/map_tiles.py), and update the map's style to match"
            )
        return f"{config.PROTOMAPS_BUILD_URL}{build['key']}", build.get('version')
