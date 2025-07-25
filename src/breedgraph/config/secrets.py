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
CSRF_EXPIRES = int(os.environ.get('CSRF_EXPIRES', 60)) # Default 1 hour

def get_graphdb_auth():
    username = os.environ['NEO4J_USERNAME']
    password = os.environ['NEO4J_PASSWORD']
    return username, password