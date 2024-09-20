from fastapi import FastAPI, Request   # todo consider dropping fastapi for starlette
#from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from ariadne.asgi import GraphQL
from ariadne import (
    EnumType,
    make_executable_schema,
    load_schema_from_path,
    snake_case_fallback_resolvers
)
from src.breedgraph.entrypoints.fastapi.graphql.resolvers import (
    graphql_query,
    graphql_mutation,
    team,
    affiliations,
    affiliation,
    user,
    account
)

from src.breedgraph import bootstrap
from src.breedgraph.domain.commands.accounts import VerifyEmail
#from src.dbtools.domain.commands.setup import LoadReadModel
from src.breedgraph.service_layer.messagebus import MessageBus
from itsdangerous import URLSafeTimedSerializer, SignatureExpired


from src.breedgraph.custom_exceptions import (
    UnauthorisedOperationError
)

from contextlib import asynccontextmanager

from src.breedgraph.config import (
    PROTOCOL,
    HOST_ADDRESS,
    HOST_PORT,
    VUE_PORT,
    GQL_API_PATH,
    SECRET_KEY,
    LOGIN_SALT,
    TOKEN_EXPIRES_MINUTES
)

from typing import Optional
from src.breedgraph.domain.model.accounts import AccountStored

# logging
import logging
logger = logging.getLogger(__name__)

#bus=None

@asynccontextmanager
async def lifespan(fast_api_app: FastAPI):
    logger.debug("Application startup")
    logger.debug("Build the messaging bus")

    bus: MessageBus = await bootstrap.bootstrap()
    app.bus = bus

    async def get_user_id(request: Request) -> Optional[AccountStored]:
        token = request.headers.get('token')
        if token is not None:
            ts = URLSafeTimedSerializer(SECRET_KEY)
            try:
                user_id = ts.loads(token, salt=LOGIN_SALT, max_age=TOKEN_EXPIRES_MINUTES * 60)
                return user_id

            except SignatureExpired as e:
                logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
                # return RedirectResponse(
                #    url=f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}")  # return redirect to front end
                raise UnauthorisedOperationError("The login token has expired")

    async def get_context_value(request: Request, _):
        logger.debug("get context value")
        return {
            "request": request,
            "bus": bus,
            "user_id": await get_user_id(request)
        }

    # create the schema instance for use in the graphql route
    #  map enums for gql
    # access_level = EnumType("AccessLevel", AccessLevel)

    logger.debug("Build graphql schema and bind")
    graphql_schema = make_executable_schema(
        load_schema_from_path("src/breedgraph/entrypoints/fastapi/graphql"),
        graphql_query,
        graphql_mutation,
        team,
        affiliations,
        affiliation,
        user,
        account,
        snake_case_fallback_resolvers
        # access_level
    )

    logger.debug("Mount graphql onto app with context values")
    fast_api_app.mount(
        f"/{GQL_API_PATH}",
        GraphQL(
            graphql_schema,
            debug=True,
            logger="ariadne",
            context_value=get_context_value
        )
    )
    logger.debug("Prepare graphql schema")

    ##logger.debug("Load read model ")
    ##await bus.handle(LoadReadModel())
    yield

    logger.info("Start shutting down")
    if bus is not None:
        if hasattr(bus.uow, "driver"):
            logger.info("Closing Neo4j driver")
            await bus.uow.driver.close()
        logger.info("Closing Redis connection pool")
        await bus.read_model.connection.aclose()
    logger.info("Finished shutting down")

logger.debug("Start FastAPI app")
app = FastAPI(lifespan=lifespan)

#logger.debug("Load auth scheme")
#oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# CORS
origins = [
    f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.debug('Prepare startup')

@app.get('/')
def read_root():
    logger.debug("Hit")
    return RedirectResponse(url=f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}")  # return redirect to front end

@app.get('/verify')
async def verify_email(token):
    await app.bus.handle(VerifyEmail(token=token))
    return RedirectResponse(url=f"{PROTOCOL}://{HOST_ADDRESS}:{HOST_PORT}/{GQL_API_PATH}")
