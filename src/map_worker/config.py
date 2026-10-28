import os
from pathlib import Path


MAP_WORKER_AUTH_TOKEN=os.environ.get("MAP_WORKER_AUTH_TOKEN")
if not MAP_WORKER_AUTH_TOKEN:
    raise ValueError("MAP_WORKER_AUTH_TOKEN environment variable is required")

API_URL=os.environ.get('API_URL', 'http://localhost:8000')

MAP_POLL_INTERVAL=int(os.environ.get('MAP_POLL_INTERVAL', 5))
# Where the worker cuts files before sending them, on a disk with room for the largest (the API's MAP_REGION_MAX_GB);
# emptied when the worker starts
MAP_WORK_PATH=os.environ.get('MAP_WORK_PATH')
if not MAP_WORK_PATH:
    raise ValueError("MAP_WORK_PATH environment variable is required")
# Where the extracts cut are kept, and sent again rather than cut again (adapters/cache.py): on the filesystem of
# MAP_WORK_PATH, and shared by the workers of several sites. Unset, none are kept.
MAP_CACHE_PATH=os.environ.get('MAP_CACHE_PATH') or None
# The go-pmtiles command (breedgraph docs/maps.md)
MAP_PMTILES_COMMAND=os.environ.get('MAP_PMTILES_COMMAND', 'pmtiles')
GEOBOUNDARIES_URL=os.environ.get('GEOBOUNDARIES_URL', 'https://www.geoboundaries.org/api/current/gbOpen')
PROTOMAPS_BUILDS_URL=os.environ.get('PROTOMAPS_BUILDS_URL', 'https://build-metadata.protomaps.dev/builds.json')
# GeoNames' files, for the place search; empty to fetch none
GEONAMES_URL=os.environ.get('GEONAMES_URL', 'https://download.geonames.org/export/dump')
# How long GeoNames' places are kept in the cache and sent again, in days: GeoNames changes daily, but little that
# matters to placing field trials
GAZETTEER_CACHE_DAYS=float(os.environ.get('GAZETTEER_CACHE_DAYS', 30))

LOG_LEVEL=os.environ.get('LOG_LEVEL', 'INFO')

LOG_BASE_PATH=Path(os.environ.get('LOG_BASE', '.'))

# Ensure log directory exists
LOG_BASE_PATH.mkdir(parents=True, exist_ok=True)

MAP_LOG=LOG_BASE_PATH / os.environ.get('MAP_LOG', 'map.log')


LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s]: %(message)s'
        },
        'named': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'map': {
            'level': "DEBUG",
            'formatter': 'named',
            'class': 'logging.FileHandler',
            'filename': MAP_LOG
        }
    },
    'loggers': {
        'root': {
            'handlers': ['map'],
            'level': LOG_LEVEL,
            'propagate': True
        },
        'httpx': {
            'handlers': ['map'],
            'level': "WARN",
            'propagate': False
        }
    }
}
