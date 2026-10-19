import os

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
# The Protomaps build regions are cut from: 'latest', or the URL of a build to pin
MAP_TILES_BUILD = os.environ.get('MAP_TILES_BUILD', 'latest')
# The go-pmtiles command that cuts the tiles; regions are not fetched while it is empty or not installed
MAP_PMTILES_COMMAND = os.environ.get('MAP_PMTILES_COMMAND', 'pmtiles')
# Country outlines, used only to cut the tiles: cached here, not served
MAP_BOUNDARIES_PATH = os.environ.get('MAP_BOUNDARIES_PATH', 'instance/map_boundaries')
# geoBoundaries' open outlines of countries and their subdivisions, by ISO 3166 alpha-3 code
GEOBOUNDARIES_URL = os.environ.get('GEOBOUNDARIES_URL', 'https://www.geoboundaries.org/api/current/gbOpen')
# The list of Protomaps' daily builds, each served at PROTOMAPS_BUILD_URL followed by its key
PROTOMAPS_BUILDS_URL = os.environ.get('PROTOMAPS_BUILDS_URL', 'https://build-metadata.protomaps.dev/builds.json')
PROTOMAPS_BUILD_URL = 'https://build.protomaps.com/'
