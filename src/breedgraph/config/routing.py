import os
# The layout template looks for DEV value to load a splash warning
# Also used in checks for which ports to access Neo4j and Redis instances, unless DB_PORT and REDIS_PORT give them
# Set to false for production or if running services on the default ports
#DEV = os.environ.get('ENVIRONMENT', 'production') == 'development'
DEV=False

PROTOCOL = os.environ.get("PROTOCOL", "http")
SITE_NAME = os.environ.get("SITE_NAME", 'BreedGraph')
HOST_ADDRESS = os.environ.get("HOST_ADDRESS", 'localhost')
HOST_PORT = os.environ.get("HOST_PORT", 8000)
GQL_API_PATH = os.environ.get("GRAPHQL_API_PATH", 'graphql')
VUE_PORT = os.environ.get("VUE_PORT", 8080)
# The path the site is served under, e.g. /demo for a demonstration site beside production on the same host, behind a
# proxy that strips it before the API sees a request; empty at the host's root. Every link the API gives starts with it
def site_path(value: str) -> str:
    """A path as SITE_PATH takes it, /demo for demo, /demo/ or /demo; empty for the host's root"""
    return ('/' + (value or '').strip('/')).rstrip('/')

SITE_PATH = site_path(os.environ.get("SITE_PATH", ''))
# What the names of the API's cookies start with, e.g. demo_ beside production on the same host: a browser sends a
# host's cookies to every path, so a site under SITE_PATH needs names of its own, as well as its cookies' path
COOKIE_PREFIX = os.environ.get("COOKIE_PREFIX", '')

MAIL_HOST = os.environ.get('MAIL_HOST')
MAIL_PORT = os.environ.get('MAIL_PORT')
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
MAIL_FROM = os.environ.get('MAIL_FROM')
MAIL_USE_TLS = bool(int(os.environ.get('MAIL_USE_TLS', 1)))
MAIL_AUTHENTICATED = bool(int(os.environ.get('MAIL_AUTHENTICATED', 1)))


def _is_default_port(port) -> bool:
    # Ports come from the environment as strings
    return str(port) in ('80', '443')

def _origin(port) -> str:
    return f'{PROTOCOL}://{HOST_ADDRESS}' if _is_default_port(port) else f'{PROTOCOL}://{HOST_ADDRESS}:{port}'

def get_base_url():
    """The API's own public address, under SITE_PATH, with a trailing slash"""
    return f'{_origin(HOST_PORT)}{SITE_PATH}/'

def get_vue_url():
    """The front end's address, under SITE_PATH, with a trailing slash. Use it for every link sent to users"""
    return f'{_origin(VUE_PORT)}{SITE_PATH}/'

def get_vue_origin():
    """The front end's origin, for CORS: its scheme, host and port, without SITE_PATH"""
    return _origin(VUE_PORT)

def cookie_name(name: str) -> str:
    """A cookie's name, with COOKIE_PREFIX"""
    return f'{COOKIE_PREFIX}{name}'

def cookie_path() -> str:
    """The path the API's cookies are set for: SITE_PATH, so that a site at the host's root isn't sent them"""
    return f'{SITE_PATH}/'

def get_download_endpoint():
    return f'{get_base_url()}download?token='

DATABASE_NAME = os.environ.get("DATABASE_NAME")  # currently only a single database available
def get_bolt_url():
    host = os.environ.get('DB_HOST', 'localhost')
    # DB_PORT for a second instance on the same machine, e.g. a hosted demo or scripts/scratch_services.sh
    port = os.environ.get('DB_PORT') or (7688 if DEV else 7687)
    return f"neo4j://{host}:{port}"

def get_redis_host_and_port():
    host = os.environ.get('REDIS_HOST', 'localhost')
    port = int(os.environ.get('REDIS_PORT') or (6380 if DEV else 6379))
    return host, port

def get_gql_url():
    base_url = get_base_url()
    return f'{base_url}/{GQL_API_PATH}/'
