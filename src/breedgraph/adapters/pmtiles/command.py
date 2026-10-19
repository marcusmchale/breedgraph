"""
The go-pmtiles command (README.md, Maps), which cuts regions out of a Protomaps build reading only the parts it needs,
and the choice of build.
"""
import asyncio
import re
import shutil
import time
from pathlib import Path
from typing import List, Tuple

import httpx

from breedgraph import config

import logging
logger = logging.getLogger(__name__)

_ARCHIVE_SIZE = re.compile(r'archive size of ([\d.]+) ?([kKMGTPE]?)B\b')
_UNITS = {'': 1, 'k': 1e3, 'K': 1e3, 'M': 1e6, 'G': 1e9, 'T': 1e12, 'P': 1e15, 'E': 1e18}
BUILDS_CACHE_SECONDS = 3600


class MapRegionError(Exception):
    """A region that could not be fetched. The message is for the log only."""


def parse_archive_size(output: str) -> int:
    """The size in bytes reported by pmtiles extract --dry-run, e.g. '... for an archive size of 454 MB'"""
    matches = _ARCHIVE_SIZE.findall(output)
    if not matches:
        raise MapRegionError(f"pmtiles reported no archive size: {output[-500:]}")
    number, unit = matches[-1]
    return int(float(number) * _UNITS[unit])


class PmtilesCommand:

    def __init__(self, command: str):
        self.command = command

    def available(self) -> bool:
        return bool(self.command) and shutil.which(self.command) is not None

    async def _run(self, *arguments: str) -> str:
        """Its output; the command is stopped if the task is cancelled"""
        process = await asyncio.create_subprocess_exec(
            self.command, *arguments, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        try:
            output, _ = await process.communicate()
        except asyncio.CancelledError:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 10)
                except TimeoutError:
                    process.kill()
            raise
        output = output.decode(errors='replace')
        if process.returncode != 0:
            raise MapRegionError(f"pmtiles {arguments[0]} exited with {process.returncode}: {output[-500:]}")
        return output

    @staticmethod
    def _options(outline: Path | None, minzoom: int, maxzoom: int) -> List[str]:
        """The region's outline, or the whole world without one, between the zooms"""
        region = [f'--region={outline}'] if outline is not None else []
        return [*region, f'--minzoom={minzoom}', f'--maxzoom={maxzoom}']

    async def size(self, build: str, outline: Path | None, minzoom: int, maxzoom: int) -> int:
        """The size in bytes of the region's file, from a dry run that reads only the build's directories"""
        output = await self._run('extract', build, '/dev/null', *self._options(outline, minzoom, maxzoom), '--dry-run')
        return parse_archive_size(output)

    async def extract(self, build: str, outline: Path | None, output: Path, minzoom: int, maxzoom: int) -> None:
        await self._run('extract', build, str(output), *self._options(outline, minzoom, maxzoom), '--quiet')


def latest_build(builds: List[dict], major: str | None = None) -> dict | None:
    """The newest build, of the given major version of the tiles, to match the world file and the map's style"""
    builds = [build for build in builds if str(build.get('key', '')).endswith('.pmtiles')]
    if major is not None:
        builds = [build for build in builds if str(build.get('version', '')).split('.')[0] == major]
    return max(builds, key=lambda build: build['key'], default=None)


class ProtomapsBuilds:
    """The build to cut regions from: config.MAP_TILES_BUILD, or the newest of Protomaps' daily builds"""

    def __init__(self, build: str = 'latest'):
        self.build = build
        self._builds: List[dict] = []
        self._read_at = 0.0

    async def _list(self) -> List[dict]:
        if time.monotonic() - self._read_at > BUILDS_CACHE_SECONDS or not self._builds:
            try:
                async with httpx.AsyncClient(timeout=30, headers={'User-Agent': 'BreedGraph'}) as client:
                    response = await client.get(config.PROTOMAPS_BUILDS_URL)
                    response.raise_for_status()
                    self._builds = response.json()
            except (httpx.HTTPError, ValueError) as e:
                raise MapRegionError(f"The list of Protomaps builds could not be read: {type(e).__name__}")
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
