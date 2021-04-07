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

MAX_WORKERS = 30  # for multithreading, set to about 5x the number of threads available.
# todo need to set up a global counter for available workers
# they are started currently in repos and in uow events queue

BREEDGRAPH_LOG = os.environ.get('BREEDGRAPH_LOG')
NEO4J_DRIVER_LOG = os.environ.get('NEO4J_DRIVER_LOG')
GRAPHQL_LOG = os.environ.get('GRAPHQL_LOG')

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
    return dict(host=host, port=port)


def get_gql_url():
    return f"https://{HOST_ADDRESS}/{GQL_API_PATH}/"


# def get_email_host_and_port():
#	host = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
#	port = 465
#	http_port = 18025 if host == 'localhost' else 8025
#	return dict(host=host, port=port, http_port=http_port)
#
