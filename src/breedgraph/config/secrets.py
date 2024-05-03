import os

SECRET_KEY = 'have-a-crack-at-it'
VERIFY_TOKEN_SALT = "slip-that-over-your-laughing-gear"
PASSWORD_RESET_SALT = "ZOMFG-How-COULD-y0u-FORGETZ"
LOGIN_SALT = "Since-you-asked-so-nicely"
TOKEN_EXPIRES_MINUTES = 10080

def get_graphdb_auth():
    username = os.environ['NEO4J_USERNAME']
    password = os.environ['NEO4J_PASSWORD']
    return username, password