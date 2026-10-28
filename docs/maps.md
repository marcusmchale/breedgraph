# Maps

Browsers contact no third party for maps: tiles come from our server, and the API answers place searches itself, from
its own copy of GeoNames' places, so no search leaves the server (Place search, below).

## The world and the regions

The tiles are cut from a [Protomaps](https://docs.protomaps.com/basemaps/downloads) build of OpenStreetMap into
`MAP_TILES_PATH`, served at `/tiles` and listed in `tiles.json`. Only the parts needed are downloaded.
- **The world** at low detail, to zoom 8 (about 560 MB), is cut by `scripts/map_tiles.py`.
- **Regions** in full detail, to zoom 15, are fetched by the API in the background (`adapters/pmtiles/map_regions.py`):
  - When a country is added, the whole country is fetched (Ireland 454 MB, Kenya 404 MB).
  - A country larger than `MAP_REGION_MAX_GB` (2) is divided into its states or provinces (ADM1 units), and a section
    is fetched when a location in it is placed on the map. A section over the cap too is fetched by its ADM2 unit
    (a county, say) instead, and one still over the cap fails as too large. Brazil (4.2 GB), France (5.5 GB) and the
    United States (17 GB) are divided.
  - Where a country's maps stand is shown under the location map (`locationsMapStatus`, open to visitors): being
    fetched, divided (with its size and the cap), or failed, with why in words for its users (the disk or
    `MAP_TILES_MAX_GB` full, a section too large); other failures are in the log. No emails are sent.
  - Countries are public, and a section shows only that some location lies within it. Sections are found on our
    server, from its copy of the outlines, so no site coordinates leave it.
  - Each region is a file, `regions/<key>.pmtiles`, with a `<key>.json` description, and each country has its extent
    for the map to show it by in `countries/<code>.json`, whether fetched whole or divided. Removing a country deletes
    its files; a section stays until its country is removed.
  - Before a fetch, a dry run gives the region's size. The fetch fails unless the disk has room for it, with 10% of
    its size and 1 GB to spare. Plan for up to `MAP_REGION_MAX_GB` per country added or section placed. With
    `MAP_TILES_MAX_GB` set, as on the demonstration site, which shares production's disk, it also fails if the
    regions' files would then take more than that together.
  - Each API process fetches one region at a time. Redis holds a lock per region, the regions under way, which resume
    after a restart, and why a region's last fetch failed. Finished regions are known from their files.
- **With the map worker** (`MAP_WORKER=1`), for an API's server without internet access, as in production: the map
  worker (`src/map_worker`, `instance/map_worker.service`), on a server with access, fetches for the API
  (`adapters/pmtiles/jobs.py`). Everything else about regions above is unchanged.
  - It polls the API's `/map_jobs/` with its own token (`MAP_WORKER_AUTH_TOKEN`) and leases jobs from Redis in two
    lanes: one for extracts, one for the rest (Protomaps' list of builds, outlines, sizes), so a long extract holds up
    no new country. It renews a job's lease (`MAP_JOB_LEASE_SECONDS`, 300) while it works, and a job whose worker
    stopped is queued again once its lease expires. One job is kept per kind and region, so an API restarted while the
    worker extracts waits for that extract rather than asking again.
  - Outlines and files come back through the API, which keeps them under names of its own beside where they go.
    Removing a country cancels its jobs: the worker stops at its next renewal.
  - With `MAP_CACHE_PATH`, the worker keeps each region it cuts (`src/map_worker/adapters/cache.py`), and sends the
    file kept when a region is asked for again with the same zooms, outline and major version of the tiles, however
    old its build. A country removed and added again, or added on the demonstration site, whose worker shares the
    cache, is then not cut again from Protomaps. The region's description (`regions/<key>.json`) names the build it
    was cut from. `scripts/map_tiles.py` takes the world file from the cache too, unless `--fresh`, and `--refresh`
    cuts regions again from the newest build, replacing those kept. The API never deletes from the cache: it holds at
    most one file per region ever asked for, so delete from it by hand if the worker server's disk needs the room.
  - Coordinates never leave the API's server: sections are found there, and a job carries only a region's key, its
    outline, a build with its version, zooms, and whether to cut it anew. The worker refuses anything but maps from
    Protomaps' builds, so a pinned `MAP_TILES_BUILD` must be one at `https://build.protomaps.com/`.
  - `scripts/map_tiles.py` goes through it too, while the API and the worker run. The API's server then needs no
    pmtiles, and the worker's needs no access to Redis or the database.

## tiles.json

`/tiles/tiles.json` (404 until the world file is cut) is what the map reads: `{attribution, updated, layers, countries}`.
Bounds in it are `[[south, west], [north, east]]`.
- The first layer is the world file, `{url, maxZoom, build}`. The others are regions, `{url, name, minZoom, maxZoom,
  bounds}`, each added once complete. Regions share the tiles along their borders, so the map draws them as one layer
  whose source takes each tile from the first region whose zooms and bounds hold it (breedview
  `composables/locations/baseMap.js`). Serve `tiles.json` without caching: BreedView reads it again while the map is
  open, when a location is selected and when it shows a country's maps arriving (`composables/locations/tilesJson.js`).
- `countries` maps each country's code to `{name, bounds}`, the extent to show it by around its main parts (east is
  above 180 for a country across the antimeridian), for every country fetched or divided. Where a country has none,
  `locationsCountryPlace(code).bounds`, from GeoNames' outlines, is the fallback.

## Place search

The location map's place search is answered by the API from [GeoNames](https://www.geonames.org)' places (CC BY 4.0,
credited under the map), kept on our server (`adapters/geonames`). **No search leaves the server: no third party
receives what anyone searches for.** Until v0.1.7, searches went to Nominatim, the OpenStreetMap Foundation's service
in the United Kingdom. Searches are not logged, and are open to visitors.
- **What is searched:** the towns of 1,000 people or more worldwide (GeoNames' `cities1000`) and every country, fetched
  when the API first starts; and every place of each country in the location trees (its own dump: villages,
  townlands, farms, hills, rivers, with their other names, in other languages or older), fetched when the country is
  added, and deleted when it is removed. A country's own places stand in for the world's towns of it. Roads,
  undersea features and places no longer there are left out. At each start the API fetches what is missing: the
  world's, and those of countries in the location trees whose places were never fetched or failed.
- **How:** a search's words are matched without case or accents. The first word (or, failing that, another) is in the
  place's names and the others in its names or those of its county, province or country, so "Ballyduff Kerry" finds
  the Ballyduff in Kerry; the last word may be the start of one, as it is typed. Whole names come first, then names
  started, then other names; then, as BreedView asks, those in the map's view, or only those (`bounded`), or only
  those of one country; then the larger and more important, and the nearer. Each result has its kind ("town",
  "farm"), its region ("Kerry, Munster") and a zoom to show it at, or for a country, its extent around its main parts,
  which `locationsCountryPlace` gives too.
- **Guards:** a search is stopped after a second, each API process runs four at a time (the rest wait up to five
  seconds, then are refused as busy), and a request makes at most five. There is no hourly limit.
- **Where they stand:** `locationsMapStatus`'s `places` says whether a country's own places are there, coming, or
  failed (with why in words for its users), and whether the world's towns stand in for them meanwhile.
- **Storage** (`GAZETTEER_PATH`, not served): one SQLite database, `gazetteer.sqlite` (SQLite's full-text search,
  FTS5), and the files it is loaded from, `places/<key>.tsv.gz`, one for the world and one per country, from which it
  is made again when a release changes its layout. Measured: the world's file 11.5 MB and 65 MB in the database,
  loaded in 6 s; Ireland's (30,000 places) 0.7 MB and 5 MB, in half a second; the United States' (2.2 million) 59 MB
  and 430 MB, written by the worker in 26 s and loaded in 33 s, with searches still answered within a few tenths of a
  second. A single letter is matched as a whole name, as the start of one would be the start of too many.
- **Fetching:** the API downloads the files from `GEONAMES_URL` itself (empty: none are fetched, and searches answer
  from what is there), or with `MAP_WORKER=1` the map worker does, as a `gazetteer` job in its quick lane, the file
  coming back through the API. The worker keeps each file in its cache (`MAP_CACHE_PATH/gazetteer`) and sends it again
  rather than downloading it while younger than `GAZETTEER_CACHE_DAYS` (30): GeoNames changes daily, but little that
  matters to a field trial's map. `scripts/map_tiles.py --gazetteer` fetches the world's and every country's again,
  from the cache, or with `--fresh` downloaded anew. Removing a country cancels its job.
- Redis holds a lock per key, the fetches under way, which resume after a restart, and why a fetch failed. A load
  is one transaction, and searches go on during it.

## Outlines and builds

Country outlines come from [geoBoundaries](https://www.geoboundaries.org) (`GEOBOUNDARIES_URL`; open licences, which
vary by country and are kept beside each file). They are cached in `MAP_BOUNDARIES_PATH`, which is not served, and used
only to cut tiles. Regions are cut from the newest Protomaps build (`PROTOMAPS_BUILDS_URL`) of the same version as the
world file, or from the build `MAP_TILES_BUILD` pins.

## The pmtiles command and the world file

The server that fetches, the API's or the map worker's, needs the `pmtiles` command from
[go-pmtiles](https://github.com/protomaps/go-pmtiles/releases) (`MAP_PMTILES_COMMAND`), a single program. Without it, or
with the setting empty, and without the map worker, no regions are fetched and the API logs a warning at startup.
Install it once (`Linux_arm64` on ARM). The release has no checksums file, but GitHub records each download's SHA-256
(the `digest` the second command prints), which the third checks:

    curl -LO https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/go-pmtiles_1.31.2_Linux_x86_64.tar.gz
    curl -s https://api.github.com/repos/protomaps/go-pmtiles/releases/tags/v1.31.2 | python3 -c 'import json, sys; print({a["name"]: a["digest"] for a in json.load(sys.stdin)["assets"]}["go-pmtiles_1.31.2_Linux_x86_64.tar.gz"])'
    sha256sum go-pmtiles_1.31.2_Linux_x86_64.tar.gz
    tar xzf go-pmtiles_1.31.2_Linux_x86_64.tar.gz pmtiles
    sudo install pmtiles /usr/local/bin/

Then cut the world file, from the newest build unless `--build` or `MAP_TILES_BUILD` names one:

    set -a; . ./breedgraph.env; set +a
    scripts/map_tiles.py

Run it again with `--fresh` now and then to refresh the world file (without it, a map worker with a cache sends the
world it keeps), and then `scripts/map_tiles.py --refresh` to fetch the regions again from the newest build.
`--regions` fetches what the API would for every country and placed location, for a first setup or after losing the
files, and `--dry-run` reports what would be fetched and its size. The script shares the API's locks, so both can run
at once. Deploying leaves `MAP_TILES_PATH`, `MAP_BOUNDARIES_PATH` and `GAZETTEER_PATH` as they are. For
development, `--world-maxzoom 6` gives a world file of about 45 MB.

## Serving the tiles

Serve the map tiles directly from `MAP_TILES_PATH`, beside the front end; nginx answers the range requests
they are read with. `tiles.json` changes as regions are fetched, so browsers check it each time they read it:

    location = /tiles/tiles.json {
        alias /opt/breedgraph/instance/map_tiles/tiles.json;
        add_header Cache-Control "no-cache";
    }
    location /tiles/ {
        alias /opt/breedgraph/instance/map_tiles/;
        add_header Cache-Control "public, max-age=86400";
    }
