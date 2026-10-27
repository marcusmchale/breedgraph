"""
What fetching maps needs from the internet (breedgraph README.md, Maps): Protomaps' list of builds, the go-pmtiles
command that cuts regions out of a build reading only the parts it needs, and geoBoundaries' outlines of countries and
their sections.

The map worker runs these for the API on a server with internet access; the API runs them itself when it fetches its
own maps (breedgraph adapters/pmtiles). So this module needs only the standard library and httpx, and reads no
environment: both pass in their settings.
"""
import asyncio
import re
import shutil
from pathlib import Path
from typing import List, Tuple

import httpx

import logging
logger = logging.getLogger(__name__)

# Each of Protomaps' daily builds is served here, followed by its key
PROTOMAPS_BUILD_URL = 'https://build.protomaps.com/'
HEADERS = {'User-Agent': 'BreedGraph'}
# what geoBoundaries says about a country's outlines that is kept beside them: its source and licence
ABOUT = ('boundaryID', 'boundaryName', 'boundaryLicense', 'licenseSource', 'buildDate')

_ARCHIVE_SIZE = re.compile(r'archive size of ([\d.]+) ?([kKMGTPE]?)B\b')
_UNITS = {'': 1, 'k': 1e3, 'K': 1e3, 'M': 1e6, 'G': 1e9, 'T': 1e12, 'P': 1e15, 'E': 1e18}


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

    async def size(self, build: str, outline: Path | None, minzoom: int, maxzoom: int, key: str | None = None) -> int:
        """
        The size in bytes of the region's file, from a dry run that reads only the build's directories.
        key names the region (or 'world'); the command doesn't need it, the map worker's jobs do.
        """
        output = await self._run('extract', build, '/dev/null', *self._options(outline, minzoom, maxzoom), '--dry-run')
        return parse_archive_size(output)

    async def extract(
            self, build: str, outline: Path | None, output: Path, minzoom: int, maxzoom: int, key: str | None = None
    ) -> None:
        await self._run('extract', build, str(output), *self._options(outline, minzoom, maxzoom), '--quiet')


def latest_build(builds: List[dict], major: str | None = None) -> dict | None:
    """The newest build, of the given major version of the tiles, to match the world file and the map's style"""
    builds = [build for build in builds if str(build.get('key', '')).endswith('.pmtiles')]
    if major is not None:
        builds = [build for build in builds if str(build.get('version', '')).split('.')[0] == major]
    return max(builds, key=lambda build: build['key'], default=None)


async def list_builds(url: str) -> List[dict]:
    """Protomaps' list of builds, each {key, version, ...}"""
    try:
        async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()
            builds = response.json()
    except (httpx.HTTPError, ValueError) as e:
        raise MapRegionError(f"The list of Protomaps builds could not be read: {type(e).__name__}")
    if not isinstance(builds, list):
        raise MapRegionError("The list of Protomaps builds is not a list")
    return builds


async def download_outlines(url: str, code: str, level: str) -> Tuple[dict, dict]:
    """
    geoBoundaries' outlines of the country with this ISO 3166 alpha-3 code (ADM0) or its sections at that level (ADM1,
    ADM2), simplified: what it says about them (ABOUT: their source and licence, which vary by country) and the
    outlines themselves, a GeoJSON FeatureCollection
    """
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True, headers=HEADERS) as client:
            response = await client.get(f"{url}/{code}/{level}/")
            if response.status_code == 404:
                raise MapRegionError(f"geoBoundaries has no {level} outlines for {code}")
            response.raise_for_status()
            about = response.json()
            response = await client.get(about['simplifiedGeometryGeoJSON'])
            response.raise_for_status()
            outlines = response.json()
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        raise MapRegionError(f"The {level} outlines for {code} could not be downloaded: {type(e).__name__}")
    if not isinstance(outlines, dict) or not outlines.get('features'):
        raise MapRegionError(f"geoBoundaries returned no {level} outlines for {code}")
    return {key: about.get(key) for key in ABOUT}, outlines
