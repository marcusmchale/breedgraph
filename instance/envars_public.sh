# Neo4j Configuration
# Although you can't have multiple db in community edition
# you might consider using the plugin from https://dozerdb.org/
# particularly for testing etc.
export ENVIRONMENT="production"  # or "development"
# Alternatively you can just change the db name here and in the neo4j conf and restart when you are doing testing
export DATABASE_NAME="neo4j"
export NEO4J_USERNAME="USERNAME_HERE"
export NEO4J_PASSWORD="PASSWORD_HERE"

# Mail host configuration
export MAIL_HOST='gmail.com'
export MAIL_PORT=465
export MAIL_USERNAME="USERNAME_HERE"
export MAIL_PASSWORD="PASSWORD_HERE"
export MAIL_USE_TLS=1

# Log files
export BREEDGRAPH_LOG="./logs/breedgraph.log"
export NEO4J_LOG="/logs/neo4j.log"
export GRAPHQL_LOG="./logs/graphql.log"
export FASTAPI_LOG="./logs/fastapi.log"
export REDIS_LOG="./logs/redis.log"
export REPOSITORIES_LOG="./logs/repositories.log"
export GRAPHQL_LOG="./logs/graphql.log"
export ARIADNE_LOG="./logs/ariadne.log"

# Secret keys
export SECRET_KEY='have-a-crack-at-it'
export VERIFY_TOKEN_SALT="slip-that-over-your-laughing-gear"
export VERIFY_EXPIRES=1440 # in minutes
export PASSWORD_RESET_SALT="ZOMFG-How-COULD-y0u-FORGETZ"
export PASSWORD_RESET_EXPIRES=60 # in minutes
export LOGIN_SALT="Since-you-asked-so-nicely"
export LOGIN_EXPIRES=10080 # in minutes
export CSRF_SALT='tell-me-who-is-asking'
export CSRF_EXPIRES=60

# Hosting environment
export PROTOCOL="http"
export SITE_NAME='BreedGraph'
export HOST_ADDRESS='localhost'
export HOST_PORT=8000
export GQL_API_PATH='graphql'
export VUE_PORT=8080