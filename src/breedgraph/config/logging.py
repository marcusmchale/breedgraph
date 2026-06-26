import os
from enum import Enum
from pathlib import Path

class Environment(Enum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"

ENVIRONMENT = Environment(os.environ.get('ENVIRONMENT', "production"))  # or "development

BASE_PATH = Path(os.environ.get('LOG_BASE', '.'))
BREEDGRAPH_LOG = BASE_PATH / os.environ.get('BREEDGRAPH_LOG', 'breedgraph.log')
ARIADNE_LOG = BASE_PATH / os.environ.get('ARIADNE_LOG', 'ariadne.log')
NEO4J_LOG = BASE_PATH / os.environ.get('NEO4J_LOG', 'neo4j.log')
REDIS_LOG = BASE_PATH / os.environ.get('REDIS_LOG', 'redis.log')

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
        'breedgraph': {
            'level': 'DEBUG',
            'formatter': 'named',
            'class': 'logging.FileHandler',
            'filename': BREEDGRAPH_LOG
        },
        'ariadne': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': ARIADNE_LOG
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
        }
    },
    'loggers': {
        'root': {
            'handlers': ['breedgraph'],
            'level': 'DEBUG',
            'propagate': True
        },
        'ariadne': {
            'handlers': ['ariadne'],
            'level': 'DEBUG',
            'propagate': False
        },
        'neo4j': {
            'handlers': ['neo4j'],
            'level': 'DEBUG',
            'propagate': False
        },
        'redis': {
            'handlers': ['redis'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
}
