import os
from pathlib import Path


ARCHIVE_AUTH_TOKEN=os.environ.get("ARCHIVE_AUTH_TOKEN")
if not ARCHIVE_AUTH_TOKEN:
    raise ValueError("ARCHIVE_AUTH_TOKEN environment variable is required")

ARCHIVE_DESTINATION=os.environ.get('ARCHIVE_DESTINATION')
if not ARCHIVE_DESTINATION:
    raise ValueError("ARCHIVE_DESTINATION environment variable is required")

API_URL=os.environ.get('API_URL', 'http://localhost:8000')
ARCHIVE_POLL_INTERVAL=os.environ.get('ARCHIVE_POLL_INTERVAL', 5)
LOG_LEVEL=os.environ.get('LOG_LEVEL', 'INFO')

LOG_BASE_PATH=Path(os.environ.get('LOG_BASE', '.'))

# Ensure log directory exists
LOG_BASE_PATH.mkdir(parents=True, exist_ok=True)

ARCHIVE_LOG=LOG_BASE_PATH / os.environ.get('ARCHIVE_LOG', 'archive.log')


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
        'archive': {
            'level': LOG_LEVEL,
            'formatter': 'named',
            'class': 'logging.FileHandler',
            'filename': ARCHIVE_LOG
        }
    },
    'loggers': {
        'root': {
            'handlers': ['archive'],
            'level': LOG_LEVEL,
            'propagate': True
        }
    }
}
