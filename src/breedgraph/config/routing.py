import os
# The layout template looks for DEV value to load a splash warning
# Also used in checks for which ports to access Neo4j and Redis instances
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
MAIL_USE_TLS = bool(int(os.environ.get('MAIL_USE_TLS', 1)))
MAIL_AUTHENTICATED = bool(int(os.environ.get('MAIL_AUTHENTICATED', 1)))

def get_base_url():
    if not HOST_PORT in [80, 443]:
        return f'{PROTOCOL}://{HOST_ADDRESS}:{HOST_PORT}/'
    else:
        return f'{PROTOCOL}://{HOST_ADDRESS}/'

def get_vue_url():
    if not VUE_PORT in [80, 443]:
        return f'{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}/'
    else:
        return f'{PROTOCOL}://{HOST_ADDRESS}/'

def get_download_endpoint():
    if not HOST_PORT in [80, 443]:
        return f'{PROTOCOL}://{HOST_ADDRESS}:{HOST_PORT}/download?token='
    else:
        return f'{PROTOCOL}://{HOST_ADDRESS}/download?token='

DATABASE_NAME = os.environ.get("DATABASE_NAME")  # currently only a single database available
def get_bolt_url():
    host = os.environ.get('DB_HOST', 'localhost')
    port = 7688 if DEV else 7687
    return f"neo4j://{host}:{port}"

def get_redis_host_and_port():
    host = os.environ.get('REDIS_HOST', 'localhost')
    port = 6380 if DEV else 6379
    return host, port

def get_gql_url():
    base_url = get_base_url()
    return f'{base_url}/{GQL_API_PATH}/'
