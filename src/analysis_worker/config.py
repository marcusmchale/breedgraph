import os
from pathlib import Path


ANALYSIS_WORKER_AUTH_TOKEN=os.environ.get("ANALYSIS_WORKER_AUTH_TOKEN")
if not ANALYSIS_WORKER_AUTH_TOKEN:
    raise ValueError("ANALYSIS_WORKER_AUTH_TOKEN environment variable is required")

API_URL=os.environ.get('API_URL', 'http://localhost:8000')

ANALYSIS_POLL_INTERVAL=int(os.environ.get('ANALYSIS_POLL_INTERVAL', 5))
LOG_LEVEL=os.environ.get('LOG_LEVEL', 'INFO')

LOG_BASE_PATH=Path(os.environ.get('LOG_BASE', '.'))

# Ensure log directory exists
LOG_BASE_PATH.mkdir(parents=True, exist_ok=True)

ANALYSIS_LOG=LOG_BASE_PATH / os.environ.get('ANALYSIS_LOG', 'analysis.log')


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
        'analysis': {
            'level': "DEBUG",
            'formatter': 'named',
            'class': 'logging.FileHandler',
            'filename': ANALYSIS_LOG
        }
    },
    'loggers': {
        'root': {
            'handlers': ['analysis'],
            'level': LOG_LEVEL,
            'propagate': True
        },
        'httpx': {
            'handlers': ['analysis'],
            'level': "WARN",
            'propagate': False
        }
    }
}
