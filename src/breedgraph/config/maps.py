import os

from map_worker.fetching import PROTOMAPS_BUILD_URL  # where each build is served, followed by its key

# Place searches on the location map go to Nominatim (OpenStreetMap's geocoder) from the server, so visitors' browsers
# contact no third party. Its usage policy asks for at most one request a second and an application identified by its
# User-Agent; the contact given in it is MAIL_FROM. https://operations.osmfoundation.org/policies/nominatim/
NOMINATIM_URL = os.environ.get('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
# Searches each user may make in an hour
GEOCODING_RATE_LIMIT_PER_HOUR = int(os.environ.get('GEOCODING_RATE_LIMIT_PER_HOUR', 120))

# Map tiles, served by us so browsers contact no third party (README.md, Maps): a low-detail world file cut by
# scripts/map_tiles.py, detailed files for regions fetched when countries are added and locations placed
# (adapters/pmtiles/map_regions.py), and tiles.json listing them. Served at /tiles, by nginx in production.
MAP_TILES_PATH = os.environ.get('MAP_TILES_PATH', 'instance/map_tiles')
# A country whose detailed tiles would be larger than this is fetched in sections (states or provinces), each when a
# location in it is placed on the map
MAP_REGION_MAX_GB = float(os.environ.get('MAP_REGION_MAX_GB', 2))
# The most the regions' files may take together, so that a site sharing a server's disk (the demonstration site) is
# held to its share: a region that would take more fails. 0 for no limit but the disk's.
MAP_TILES_MAX_GB = float(os.environ.get('MAP_TILES_MAX_GB', 0))
# The Protomaps build regions are cut from: 'latest', or the URL of a build to pin
MAP_TILES_BUILD = os.environ.get('MAP_TILES_BUILD', 'latest')
# The go-pmtiles command that cuts the tiles; regions are not fetched while it is empty or not installed
MAP_PMTILES_COMMAND = os.environ.get('MAP_PMTILES_COMMAND', 'pmtiles')
# Country outlines, used only to cut the tiles: cached here, not served
MAP_BOUNDARIES_PATH = os.environ.get('MAP_BOUNDARIES_PATH', 'instance/map_boundaries')
# Whether the map worker (map_worker, on a server with internet access) fetches what regions need, rather than the API
# itself, which then needs neither the pmtiles command nor internet access for maps (adapters/pmtiles/jobs.py)
MAP_WORKER = bool(int(os.environ.get('MAP_WORKER', 0)))
# The map worker's token for the routes it polls, /map_jobs/
MAP_WORKER_AUTH_TOKEN = os.environ.get('MAP_WORKER_AUTH_TOKEN', '')
# How long the map worker's lease on a job lasts unrenewed: the job of a worker that stopped is queued again after it
MAP_JOB_LEASE_SECONDS = int(os.environ.get('MAP_JOB_LEASE_SECONDS', 300))
# geoBoundaries' open outlines of countries and their subdivisions, by ISO 3166 alpha-3 code
GEOBOUNDARIES_URL = os.environ.get('GEOBOUNDARIES_URL', 'https://www.geoboundaries.org/api/current/gbOpen')
# The list of Protomaps' daily builds, each served at PROTOMAPS_BUILD_URL followed by its key
PROTOMAPS_BUILDS_URL = os.environ.get('PROTOMAPS_BUILDS_URL', 'https://build-metadata.protomaps.dev/builds.json')
