"""
Outlines of countries and their sections from geoBoundaries (config.GEOBOUNDARIES_URL; open licences, which vary by
country and are kept with each file). They are used only to cut tiles, never shown, and are cached in
config.MAP_BOUNDARIES_PATH, which is not served.
"""
import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from breedgraph import config
from map_worker.fetching import download_outlines
from .command import MapRegionError
from .regions import Region, write_json

import logging
logger = logging.getLogger(__name__)


def _load_features(path: Path) -> List[dict]:
    return json.loads(path.read_text()).get('features') or []


class GeoBoundaries:

    def __init__(self, path: Path):
        self.path = path
        # one per file, so that waiting for one country's outlines holds up no other's
        self._downloading: Dict[Path, asyncio.Lock] = defaultdict(asyncio.Lock)

    def level_file(self, code: str, level: str) -> Path:
        return self.path / f'{code}-{level}.geojson'

    def outline_file(self, region: Region) -> Path:
        """The outline pmtiles cuts a region with: a country's own file, or a section's feature saved alone"""
        if region.shape_id is None:
            return self.level_file(region.code, region.level)
        return self.path / f'{region.key}.geojson'

    async def features(self, code: str, level: str) -> List[dict]:
        """The outlines of the country (ADM0) or its sections at that level, downloaded once"""
        path = self.level_file(code, level)
        async with self._downloading[path]:
            if not path.exists():
                await self._download(code, level, path)
        return await asyncio.to_thread(_load_features, path)

    async def _download(self, code: str, level: str, path: Path) -> None:
        """Write the level's file, path: here downloaded, by the map worker's jobs for the API (jobs.py)"""
        about, outlines = await download_outlines(config.GEOBOUNDARIES_URL, code, level)
        self.save(code, level, about, outlines)

    def save(self, code: str, level: str, about: dict, outlines: dict) -> None:
        """Keep the outlines of a country or its sections at a level, with what geoBoundaries says of their licence"""
        if not isinstance(outlines, dict) or not outlines.get('features'):
            raise MapRegionError(f"geoBoundaries returned no {level} outlines for {code}")
        path = self.level_file(code, level)
        self.path.mkdir(parents=True, exist_ok=True)
        write_json(path.with_suffix('.json'), about)
        write_json(path, outlines)
        logger.info(f"Kept the {level} outlines for {code} ({len(outlines['features'])} units)")

    def save_section(self, region: Region, feature: dict) -> None:
        """Keep a section's outline alone, for cutting it and naming it"""
        path = self.outline_file(region)
        if not path.exists():
            self.path.mkdir(parents=True, exist_ok=True)
            write_json(path, {'type': 'FeatureCollection', 'features': [
                {'type': 'Feature', 'properties': feature.get('properties') or {}, 'geometry': feature['geometry']}
            ]})

    async def outline(self, region: Region) -> Tuple[Path, List[dict]]:
        """The file pmtiles cuts the region with, and the region's features in it (one, unless a country has more)"""
        if region.shape_id is None:
            return self.level_file(region.code, region.level), await self.features(region.code, region.level)
        path = self.outline_file(region)
        if not path.exists():
            features = await self.features(region.code, region.level)
            feature = next((f for f in features if (f.get('properties') or {}).get('shapeID') == region.shape_id), None)
            if feature is None:
                raise MapRegionError(f"{region.key} is not among the {region.level} outlines for {region.code}")
            self.save_section(region, feature)
        return path, await asyncio.to_thread(_load_features, path)
