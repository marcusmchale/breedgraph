#!/usr/bin/env python3
"""
Cut the map tiles BreedGraph serves (README.md, Maps) from a Protomaps build of OpenStreetMap, so that browsers load
maps from our server and contact no third party:
  - world.pmtiles: the whole world at low detail, to --world-maxzoom (8, about 560 MB);
  - regions.pmtiles: full detail, from the next zoom to --regions-maxzoom (15), in the cells of a grid of
    --cell-degrees (1) that come within --padding-km (25) of a location with coordinates (adapters/pmtiles/regions.py:
    the files are served to anyone, so they show which cells hold locations, private ones included);
  - tiles.json, listing them for the location map.
Only the parts needed are downloaded. Each file is written under a temporary name and replaced once complete, so it
can run while the files are served. Run it again when new field sites are added, or from cron, which also refreshes
the map data; --regions-only leaves the world file as it is.

Needs the pmtiles command (https://github.com/protomaps/go-pmtiles/releases) and a build: one of Protomaps' daily
builds, https://build.protomaps.com/YYYYMMDD.pmtiles, kept for about a week (https://maps.protomaps.com/builds).

Usage, with the instance env files sourced:
    python scripts/map_tiles.py --build https://build.protomaps.com/YYYYMMDD.pmtiles [--regions-only] [--dry-run]
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import AsyncGraphDatabase

from breedgraph import config
from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME
from breedgraph.adapters.pmtiles import region_cells, region_geojson, cells_bounds

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ATTRIBUTION = '© OpenStreetMap contributors, Protomaps'

COORDINATES = """
    MATCH (coordinate: Coordinate)-[:COORDINATE_OF]->(:Location)
    WHERE coordinate.latitude IS NOT NULL AND coordinate.longitude IS NOT NULL
    RETURN DISTINCT coordinate.latitude AS latitude, coordinate.longitude AS longitude
"""


async def read_coordinates() -> list[tuple[float, float]]:
    driver = AsyncGraphDatabase.driver(get_bolt_url(), auth=get_graphdb_auth())
    try:
        async with driver.session(database=DATABASE_NAME) as session:
            result = await session.run(COORDINATES)
            return [(record['latitude'], record['longitude']) async for record in result]
    finally:
        await driver.close()


def extract(pmtiles: str, build: str, output: Path, dry_run: bool, *options: str) -> None:
    """pmtiles extract into a temporary file beside output, then replace output with it"""
    temporary = output.with_name(f".{output.name}.partial")
    command = [pmtiles, 'extract', build, '/dev/null' if dry_run else str(temporary), *options]
    if dry_run:
        command.append('--dry-run')
    logger.info(' '.join(command))
    subprocess.run(command, check=True)
    if not dry_run:
        os.replace(temporary, output)


def write_json(path: Path, content: dict) -> None:
    temporary = path.with_name(f".{path.name}.partial")
    temporary.write_text(json.dumps(content, indent=2))
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--build', required=True, help="a Protomaps build, e.g. https://build.protomaps.com/YYYYMMDD.pmtiles")
    parser.add_argument('--out', default=config.MAP_TILES_PATH, help="where the tiles are served from (MAP_TILES_PATH)")
    parser.add_argument('--pmtiles', default='pmtiles', help="the pmtiles command")
    parser.add_argument('--world-maxzoom', type=int, default=8)
    parser.add_argument('--regions-maxzoom', type=int, default=15)
    parser.add_argument('--padding-km', type=float, default=25)
    parser.add_argument('--cell-degrees', type=float, default=1)
    parser.add_argument('--regions-only', action='store_true', help="keep the world file as it is")
    parser.add_argument('--dry-run', action='store_true', help="report what would be downloaded, writing nothing")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    world = out / 'world.pmtiles'
    regions = out / 'regions.pmtiles'

    world_maxzoom = args.world_maxzoom
    if not args.regions_only:
        extract(args.pmtiles, args.build, world, args.dry_run, f'--maxzoom={world_maxzoom}')
    elif world.exists() and (out / 'tiles.json').exists():
        # the world file kept, at the zoom it was cut to
        world_maxzoom = json.loads((out / 'tiles.json').read_text())['layers'][0]['maxZoom']
    else:
        logger.error(f"{world} or tiles.json is missing, so the world file can't be kept: run without --regions-only")
        return 1

    cells = region_cells(asyncio.run(read_coordinates()), padding_km=args.padding_km, cell_degrees=args.cell_degrees)
    logger.info(f"{len(cells)} cells of {args.cell_degrees} degrees hold locations")
    layers = [{'url': world.name, 'maxZoom': world_maxzoom}]
    if cells:
        with tempfile.NamedTemporaryFile('w', suffix='.geojson', delete=False) as region_file:
            json.dump(region_geojson(cells, args.cell_degrees), region_file)
        try:
            extract(
                args.pmtiles, args.build, regions, args.dry_run, f'--region={region_file.name}',
                f'--minzoom={world_maxzoom + 1}', f'--maxzoom={args.regions_maxzoom}'
            )
        finally:
            os.unlink(region_file.name)
        layers.append({
            'url': regions.name,
            'minZoom': world_maxzoom + 1,
            'maxZoom': args.regions_maxzoom,
            'bounds': cells_bounds(cells, args.cell_degrees)
        })

    if args.dry_run:
        logger.info(f"Would write {out / 'tiles.json'} with layers {layers}")
        return 0
    if not cells and regions.exists():
        regions.unlink()
    write_json(out / 'tiles.json', {
        'attribution': ATTRIBUTION,
        'build': args.build,
        'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'layers': layers
    })
    logger.info(f"Wrote the map tiles to {out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
