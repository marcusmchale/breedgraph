import os
from passlib.context import CryptContext

# The layout template looks for DEV value to load a splash warning
# Also used in checks for which ports to access Neo4j and Redis instances
# Set to false for production
DEV = False

PROTOCOL = "http"
SITE_NAME = 'BreedGraph'
HOST_ADDRESS = 'localhost'
HOST_PORT = '8000'
GQL_API_PATH = 'graphql'
VUE_PORT = '8080'

DATABASE_NAME = os.environ.get("DATABASE_NAME")

MAX_WORKERS = 30  # for multithreading, set to about 5x the number of threads available.
# todo need to set up a global counter for available workers
# they are started currently in repos and in uow events queue
N_EVENT_HANDLERS = 3


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = 'have-a-crack-at-it'
CONFIRM_TOKEN_SALT = "slip-that-over-your-laughing-gear"
PASSWORD_RESET_SALT = "ZOMFG-How-COULD-y0u-FORGETZ"
TOKEN_EXPIRES_MINUTES = 10080

MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 465
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = 'breedcafsdb@gmail.com'


def get_bolt_url():
    host = os.environ.get('DB_HOST', 'localhost')
    port = 7688 if DEV else 7687
    return f"neo4j://{host}:{port}"


def get_graphdb_auth():
    username = os.environ['NEO4J_USERNAME']
    password = os.environ['NEO4J_PASSWORD']
    return username, password


def get_redis_host_and_port():
    host = os.environ.get('REDIS_HOST', 'localhost')
    port = 6380 if DEV else 6379
    return host, port


def get_gql_url():
    return f"https://{HOST_ADDRESS}/{GQL_API_PATH}/"


# def get_email_host_and_port():
#	host = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
#	port = 465
#	http_port = 18025 if host == 'localhost' else 8025
#	return dict(host=host, port=port, http_port=http_port)
#

DBTOOLS_LOG = os.environ.get('DBTOOLS_LOG')
NEO4J_LOG = os.environ.get('NEO4J_LOG')
GRAPHQL_LOG = os.environ.get('GRAPHQL_LOG')
FASTAPI_LOG = os.environ.get('FASTAPI_LOG')
REDIS_LOG = os.environ.get('REDIS_LOG')


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
        'dbtools': {
            'level': 'DEBUG',
            'formatter': 'named',
            'class': 'logging.FileHandler',
            'filename': DBTOOLS_LOG
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
        'connection': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': REDIS_LOG
        }
    },
    'loggers': {
        'root': {
            'handlers': ['dbtools'],
            'level': 'DEBUG',
            'propagate': True
        },
        'src.dbtools.entrypoints.fastapi.graphql': {
            'handlers': ['graphql'],
            'level': 'DEBUG',
            'propagate': True
        },
        'src.dbtools.adapters': {
            'handlers': ['connection'],
            'level': 'DEBUG',
            'propagate': False
        },
        'neo4j': {
            'handlers': ['neo4j'],
            'level': 'DEBUG',
            'propagate': False
        },
    }
}

