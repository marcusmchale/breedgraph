import os
from enum import Enum
from pathlib import Path
import logging

class Environment(Enum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"

ENVIRONMENT = Environment(os.environ.get('ENVIRONMENT', 'production'))  # or "development
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')
BASE_PATH = Path(os.environ.get('LOG_BASE', '.'))
BREEDGRAPH_LOG = BASE_PATH / os.environ.get('BREEDGRAPH_LOG', 'breedgraph.log')
GRAPHQL_LOG = BASE_PATH / os.environ.get('GRAPHQL_LOG', 'graphql.log')
NEO4J_LOG = BASE_PATH / os.environ.get('NEO4J_LOG', 'neo4j.log')
REDIS_LOG = BASE_PATH / os.environ.get('REDIS_LOG', 'redis.log')
ACCESS_LOG = BASE_PATH / os.environ.get('ACCESS_LOG', 'access.log')


# This filter is to remove the frequent polling of selected endpoints from the logs
class IgnoreAccessPaths(logging.Filter):
    ignored_paths = {
        "/archive/retrieval_pending",
        "/archive/archival_pending",
        "/archive/deletion_pending"
    }
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            path = record.args[2]
        except (IndexError, TypeError):
            return True

        return path not in self.ignored_paths


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
    'filters': {
        'ignore_polling': {
            '()': IgnoreAccessPaths
        }
    },
    'handlers': {
        'breedgraph': {
            'level': 'DEBUG',
            'formatter': 'named',
            'class': 'logging.FileHandler',
            'filename': BREEDGRAPH_LOG
        },
        'graphql': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': GRAPHQL_LOG
        },
        'neo4j': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': NEO4J_LOG
        },
        'redis': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': REDIS_LOG
        },
        'access': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': ACCESS_LOG,
            'filters': ['ignore_polling']
        },
    },
    'root': {
        'handlers': ['breedgraph'],
        'level': LOG_LEVEL,
        'propagate': True
    },
    'loggers': {
        'breedgraph.entrypoints.fastapi.graphql': {
            'handlers': ['graphql'],
            'level': LOG_LEVEL,
            'propagate': False
        },
        'neo4j': {
            'handlers': ['neo4j'],
            'level': LOG_LEVEL,
            'propagate': False
        },
        'breedgraph.adapters.redis': {
            'handlers': ['redis'],
            'level': LOG_LEVEL,
            'propagate': False
        },
        'uvicorn.access': {
            'handlers': ['access'],
            'level': LOG_LEVEL,
            'propagate': False
        }
    }
}
