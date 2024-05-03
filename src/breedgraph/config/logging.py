import os

ARIADNE_LOG = os.environ.get('ARIADNE_LOG')
NEO4J_LOG = os.environ.get('NEO4J_LOG')
REDIS_LOG = os.environ.get('REDIS_LOG')

BREEDGRAPH_LOG = os.environ.get('BREEDGRAPH_LOG')
GRAPHQL_LOG = os.environ.get('GRAPHQL_LOG')
REPOSITORIES_LOG = os.environ.get('REPOSITORIES_LOG')

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
        },
        'repositories': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': REPOSITORIES_LOG
        },
        'graphql': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': GRAPHQL_LOG
        }
    },
    'loggers': {
        'root': {
            'handlers': ['breedgraph'],
            'level': 'DEBUG',
            'propagate': True
        },
        'neo4j': {
            'handlers': ['neo4j'],
            'level': 'DEBUG',
            'propagate': False
        },
        'ariadne': {
            'handlers': ['ariadne'],
            'level': 'DEBUG',
            'propagate': False
        },
        'src.dbtools.adapters.repositories': {
            'handlers': ['repositories'],
            'level': 'DEBUG',
            'propagate': False
        },
        'src.dbtools.entrypoints.fastapi.graphql': {
            'handlers': ['graphql'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
}
