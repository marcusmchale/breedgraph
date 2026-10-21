import os

# todo, consider providing default values for development (provide as second argument to get)
SECRET_KEY = os.environ.get('SECRET_KEY')

VERIFY_TOKEN_SALT = os.environ.get('VERIFY_TOKEN_SALT')
VERIFY_EXPIRES = int(os.environ.get('VERIFY_EXPIRES', 1440)) # default 24 hours

PASSWORD_RESET_SALT = os.environ.get('PASSWORD_RESET_SALT')
PASSWORD_RESET_EXPIRES = int(os.environ.get('PASSWORD_RESET_EXPIRES', 1440)) # default 24 hours

LOGIN_SALT = os.environ.get('LOGIN_SALT')
LOGIN_EXPIRES = int(os.environ.get('LOGIN_EXPIRES', 10080)) # default 7 days

CSRF_SALT = os.environ.get('CSRF_SALT')
CSRF_EXPIRES = int(os.environ.get('CSRF_EXPIRES', 60 * 60)) # Default 1 hour

# What a browser's user accepted, the Terms of Use and study licences, as one signed token per identity in a cookie
# (docs/licences.md §4). Required: the API refuses to start without the salt.
ACCEPTANCE_SALT = os.environ.get('ACCEPTANCE_SALT')
ACCEPTANCE_EXPIRES_SIGNED_IN = int(os.environ.get('ACCEPTANCE_EXPIRES_SIGNED_IN', 525600)) # default 365 days
ACCEPTANCE_EXPIRES_ANONYMOUS = int(os.environ.get('ACCEPTANCE_EXPIRES_ANONYMOUS', 10080)) # default 7 days

def get_graphdb_auth():
    username = os.environ['NEO4J_USERNAME']
    password = os.environ['NEO4J_PASSWORD']
    return username, password