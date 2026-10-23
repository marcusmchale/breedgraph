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

def get_base_url():
    """The API's own address, with a trailing slash"""
    if not _is_default_port(HOST_PORT):
        return f'{PROTOCOL}://{HOST_ADDRESS}:{HOST_PORT}/'
    else:
        return f'{PROTOCOL}://{HOST_ADDRESS}/'

def get_vue_url():
    """The front end's address, with a trailing slash. Use it for every link sent to users"""
    if not _is_default_port(VUE_PORT):
        return f'{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}/'
    else:
        return f'{PROTOCOL}://{HOST_ADDRESS}/'

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
