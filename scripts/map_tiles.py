#!/usr/bin/env python3
"""
Cut the map tiles BreedGraph serves (docs/maps.md) from a Protomaps build of OpenStreetMap, so that browsers load
maps from our server and contact no third party.

By default it cuts world.pmtiles, the whole world at low detail to --world-maxzoom (8, about 560 MB), and writes
world.json and tiles.json. The API then fetches detailed maps in the background: a country's when it is added, or for
a country too large, a section's when a location in it is placed (adapters/pmtiles/map_regions.py).
  --regions  fetches, as the API would, the detailed maps of every country in the database and of the sections where
             located locations lie, keeping those already fetched: for a first setup, or after losing the files.
  --refresh  fetches every region again from the newest build.
  --fresh    cuts the world anew from the newest build. Without it, the map worker sends the world it keeps
             (MAP_CACHE_PATH) when that is of the same zoom and major version, as for a second site.
  --gazetteer  fetches the place search's places (adapters/geonames, docs/maps.md, Place search) again: the world's
             towns and those of every country in the database, from the map worker's cache, or with --fresh
             downloaded anew. The API fetches those it lacks at each start, so this is for refreshing them.
  --dry-run  reports what would be fetched and its size.
Only the parts needed are downloaded. Each file is written under a temporary name and replaced once complete, so it
can run while the files are served, and while the API runs: they share its locks in Redis.

Needs the pmtiles command (docs/maps.md) and a build: by default (MAP_TILES_BUILD=latest) the newest of
Protomaps' daily builds, each kept for about a week (https://maps.protomaps.com/builds). With MAP_WORKER=1, as on a
server without internet access, the map worker fetches instead (adapters/pmtiles/jobs.py): the API and the worker must
be running, as the files come back through the API to MAP_TILES_PATH, the only --out then.

Usage, with the instance env files sourced:
    python scripts/map_tiles.py [--world-maxzoom 8] [--build https://build.protomaps.com/YYYYMMDD.pmtiles] [--fresh] [--dry-run]
    python scripts/map_tiles.py --regions [--dry-run]
    python scripts/map_tiles.py --refresh [--dry-run]
    python scripts/map_tiles.py --gazetteer [--fresh] [--dry-run]
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import AsyncGraphDatabase

from breedgraph import config
from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME
from breedgraph.adapters.redis import RedisStateStore
from breedgraph.adapters.geonames import GeoNamesGazetteer
from breedgraph.adapters.geonames.index import WORLD as WORLD_PLACES
from breedgraph.adapters.pmtiles import PmtilesMapRegions, Outcome, Region, MapRegionError
from breedgraph.adapters.pmtiles.command import PmtilesCommand, ProtomapsBuilds
from breedgraph.adapters.pmtiles.jobs import sources, WORLD
from breedgraph.adapters.pmtiles.regions import WORLD_JSON, read_json, read_sidecars, write_json, write_tiles_json

import logging
from breedgraph.config.logging import log_to_console
logger = logging.getLogger(__name__)

# Countries are the roots of location trees; their located locations, by the country's code
LOCATED_LOCATIONS = """
    MATCH (country: Location) WHERE NOT (country)<-[:INCLUDES_LOCATION]-(:Location) AND country.code IS NOT NULL
    OPTIONAL MATCH (country)-[:INCLUDES_LOCATION*]->(:Location)<-[:COORDINATE_OF]-(coordinate: Coordinate)
    WHERE coordinate.latitude IS NOT NULL AND coordinate.longitude IS NOT NULL
    WITH country, coordinate
    RETURN country.code AS code, [point IN collect(DISTINCT [coordinate.latitude, coordinate.longitude]) WHERE point[0] IS NOT NULL] AS points
    ORDER BY code
"""


async def read_located_locations() -> dict[str, list[tuple[float, float]]]:
    driver = AsyncGraphDatabase.driver(get_bolt_url(), auth=get_graphdb_auth())
    try:
        async with driver.session(database=DATABASE_NAME) as session:
            result = await session.run(LOCATED_LOCATIONS)
            return {record['code']: [tuple(point) for point in record['points']] async for record in result}
    finally:
        await driver.close()


def gigabytes(size: int) -> str:
    return f"{size / 10 ** 9:.2f} GB"


async def cut_world(args, out: Path, pmtiles: PmtilesCommand, builds: ProtomapsBuilds) -> int:
    build, version = await builds.latest()
    world = out / 'world.pmtiles'
    if args.dry_run:
        size = await pmtiles.size(build, None, 0, args.world_maxzoom, key=WORLD)
        logger.info(f"Would cut {world} to zoom {args.world_maxzoom} from {build}: {gigabytes(size)}")
        return 0
    partial = out / '.world.pmtiles.partial'
    logger.info(f"Cutting {world} to zoom {args.world_maxzoom} from {build}")
    cut = await pmtiles.extract(
        build, None, partial, 0, args.world_maxzoom, key=WORLD, version=version, fresh=args.fresh
    )
    if cut is not None and cut[0] != build:
        logger.info(f"The map worker sent the world it keeps, cut from {cut[0]} (--fresh cuts it anew)")
    if cut is not None:
        build, version = cut
    os.replace(partial, world)
    write_json(out / WORLD_JSON, {
        'url': world.name,
        'maxZoom': args.world_maxzoom,
        'build': build,
        'version': version,
        'updated': datetime.now(timezone.utc).isoformat(timespec='seconds')
    })
    write_tiles_json(out)
    major = version.split('.')[0] if version else None
    stale = [
        sidecar['key'] for sidecar in read_sidecars(out)
        if sidecar['minZoom'] != args.world_maxzoom + 1
        or (major and sidecar.get('version') and sidecar['version'].split('.')[0] != major)
    ]
    if stale:
        logger.warning(
            f"{len(stale)} regions start at another zoom than the world file ends, or are of another version of the "
            f"tiles: run --refresh"
        )
    logger.info(f"Wrote the world file and tiles.json to {out}")
    return 0


async def fetch_regions(args, regions: PmtilesMapRegions) -> int:
    failed = 0
    for code, points in (await read_located_locations()).items():
        country = Region(code)
        try:
            size = await regions.size(country)
            sections = await regions.sections(code, points) if size > regions.max_bytes and points else []
        except MapRegionError as e:
            logger.error(f"{code}: {e}")
            failed += 1
            continue
        if size <= regions.max_bytes:
            logger.info(f"{code}: the whole country, {gigabytes(size)}")
        else:
            logger.info(f"{code}: divided ({gigabytes(size)}), {len(sections)} sections hold its {len(points)} located points")
        for section, section_size in sections:
            logger.info(f"  {section.key}: {gigabytes(section_size)}" + (" is too large" if section_size > regions.max_bytes else ""))
        if args.dry_run:
            continue
        outcomes = [await regions.fetch_now(country)]
        outcomes += [await regions.fetch_now(section) for section, section_size in sections if section_size <= regions.max_bytes]
        failed += outcomes.count(Outcome.FAILED)
    return 1 if failed else 0


async def refresh_regions(args, regions: PmtilesMapRegions) -> int:
    failed = 0
    for sidecar in read_sidecars(regions.tiles_path):
        region = Region.from_key(sidecar['key'])
        if args.dry_run:
            logger.info(f"Would fetch {region.key} again, now {gigabytes(await regions.size(region, fresh=True))}")
        elif await regions.fetch_now(region, refresh=True) is Outcome.FAILED:
            failed += 1
    return 1 if failed else 0


async def fetch_places(args, state_store: RedisStateStore) -> int:
    gazetteer = GeoNamesGazetteer(state_store)
    if not gazetteer.worker and not gazetteer.geonames_url:
        logger.error("GEONAMES_URL is empty, and without MAP_WORKER the places are downloaded from it")
        return 1
    keys = [WORLD_PLACES, *sorted(await read_located_locations())]
    if args.dry_run:
        logger.info(f"Would fetch the places of {', '.join(keys)}" + (", downloaded anew" if args.fresh else ""))
        return 0
    await gazetteer.open()
    failed = 0
    for key in keys:
        if await gazetteer.fetch_now(key, fresh=args.fresh):
            logger.info(f"{key}: its places are loaded")
        elif key in await state_store.get_gazetteer_failures():
            logger.error(f"{key}: its places could not be fetched (the log says why)")
            failed += 1
        else:
            logger.info(f"{key}: its places were fetched by another process, as the API's")
    return 1 if failed else 0


async def run(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    world = not args.regions and not args.refresh and not args.gazetteer
    if (args.regions or args.refresh) and read_json(out / WORLD_JSON) is None:
        logger.error(f"There is no world file in {out}: cut it first, without --regions or --refresh")
        return 1
    if config.MAP_WORKER:
        logger.info("The map worker fetches: the API and the map worker must be running")
    # the regions' requests and locks, and the map worker's jobs, are kept in Redis
    state_store = await RedisStateStore.create() if config.MAP_WORKER or not world else None
    try:
        if args.gazetteer:
            return await fetch_places(args, state_store)
        if world:
            pmtiles, builds, _ = sources(
                state_store, config.MAP_WORKER, args.pmtiles, args.build, Path(config.MAP_BOUNDARIES_PATH)
            )
            return await cut_world(args, out, pmtiles, builds)
        regions = PmtilesMapRegions(state_store, command=args.pmtiles, tiles_path=out, build=args.build)
        return await (fetch_regions if args.regions else refresh_regions)(args, regions)
    finally:
        if state_store is not None:
            await state_store.connection.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--regions', action='store_true', help="fetch the regions of every country and located location")
    action.add_argument('--refresh', action='store_true', help="fetch every region again from the newest build")
    action.add_argument('--gazetteer', action='store_true', help="fetch the place search's places again")
    parser.add_argument('--build', default=config.MAP_TILES_BUILD, help="'latest', or a Protomaps build's URL (MAP_TILES_BUILD)")
    parser.add_argument('--out', default=config.MAP_TILES_PATH, help="where the tiles are served from (MAP_TILES_PATH)")
    parser.add_argument('--pmtiles', default=config.MAP_PMTILES_COMMAND or 'pmtiles', help="the pmtiles command (MAP_PMTILES_COMMAND)")
    parser.add_argument('--world-maxzoom', type=int, default=8)
    parser.add_argument('--fresh', action='store_true', help="cut the world, or download the places, anew, rather than take what the map worker keeps")
    parser.add_argument('--dry-run', action='store_true', help="report what would be fetched and its size, fetching nothing")
    args = parser.parse_args()
    if config.MAP_WORKER:
        if Path(args.out).resolve() != Path(config.MAP_TILES_PATH).resolve():
            logger.error("With MAP_WORKER the map worker's files come back to MAP_TILES_PATH, so --out must be it")
            return 1
    elif not args.gazetteer and not PmtilesCommand(args.pmtiles).available():
        logger.error(f"The pmtiles command ({args.pmtiles}) is not installed (docs/maps.md)")
        return 1
    return asyncio.run(run(args))


if __name__ == '__main__':
    log_to_console()
    sys.exit(main())
