"""What the map worker does for each kind of job, with the internet access the API's server lacks"""
import json
from pathlib import Path

from map_worker.domain.job import MapJob
from map_worker.fetching import PmtilesCommand, list_builds, download_outlines

import logging
logger = logging.getLogger(__name__)


class MapHandlers:

    def __init__(self, pmtiles: PmtilesCommand, work_path: Path, geoboundaries_url: str, builds_url: str):
        self.pmtiles = pmtiles
        self.work_path = work_path
        self.geoboundaries_url = geoboundaries_url
        self.builds_url = builds_url

    def clear(self) -> None:
        """Delete what a worker stopped part way left behind"""
        self.work_path.mkdir(parents=True, exist_ok=True)
        for path in self.work_path.iterdir():
            if path.suffix in ('.geojson', '.pmtiles') and path.is_file():
                path.unlink()

    async def handle(self, job: MapJob) -> dict | Path:
        """A quick job's result, or an extract's file, which the caller deletes once sent"""
        return await getattr(self, job.kind)(job)

    async def builds(self, job: MapJob) -> dict:
        builds = await list_builds(self.builds_url)
        return {'builds': [
            {'key': build['key'], 'version': build.get('version')}
            for build in builds if isinstance(build, dict) and 'key' in build
        ]}

    async def outlines(self, job: MapJob) -> dict:
        about, outlines = await download_outlines(self.geoboundaries_url, job.payload['code'], job.payload['level'])
        return {'about': about, 'outlines': outlines}

    def _outline(self, job: MapJob) -> Path | None:
        """The region's outline in a file for pmtiles' --region, or None for the world"""
        if job.payload['outline'] is None:
            return None
        path = self.work_path / f'{job.kind}-{job.key}.geojson'
        path.write_text(json.dumps(job.payload['outline']))
        return path

    async def size(self, job: MapJob) -> dict:
        outline = self._outline(job)
        try:
            size = await self.pmtiles.size(job.payload['build'], outline, job.payload['minzoom'], job.payload['maxzoom'])
        finally:
            if outline is not None:
                outline.unlink(missing_ok=True)
        return {'size': size}

    async def extract(self, job: MapJob) -> Path:
        outline = self._outline(job)
        output = self.work_path / f'{job.key}.pmtiles'
        logger.info(f"Extracting {job.key} from {job.payload['build']}")
        try:
            await self.pmtiles.extract(
                job.payload['build'], outline, output, job.payload['minzoom'], job.payload['maxzoom']
            )
        except BaseException:
            output.unlink(missing_ok=True)
            raise
        finally:
            if outline is not None:
                outline.unlink(missing_ok=True)
        return output
