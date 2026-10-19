import os

# Place searches on the location map go to Nominatim (OpenStreetMap's geocoder) from the server, so visitors' browsers
# contact no third party. Its usage policy asks for at most one request a second and an application identified by its
# User-Agent; the contact given in it is MAIL_FROM. https://operations.osmfoundation.org/policies/nominatim/
NOMINATIM_URL = os.environ.get('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
# Searches each user may make in an hour
GEOCODING_RATE_LIMIT_PER_HOUR = int(os.environ.get('GEOCODING_RATE_LIMIT_PER_HOUR', 120))

# Map tiles, served by us so browsers contact no third party: files cut from Protomaps' OpenStreetMap builds by
# scripts/map_tiles.py, with a tiles.json listing them. Served at /tiles, by nginx in production (README.md, Maps).
MAP_TILES_PATH = os.environ.get('MAP_TILES_PATH', 'instance/map_tiles')
