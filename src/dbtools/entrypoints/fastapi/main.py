from src.dbtools.domain.model.accounts import AffiliationLevel

from fastapi import FastAPI, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from ariadne.asgi import GraphQL
from src.dbtools.config import (
    PROTOCOL,
    HOST_ADDRESS,
    VUE_PORT,
    GQL_API_PATH,
    LOG_CONFIG
)
from ariadne import (
    EnumType,
    QueryType,
    MutationType,
    make_executable_schema,
    load_schema_from_path,
    snake_case_fallback_resolvers
)

import logging.config

from src.dbtools import bootstrap
from src.dbtools.domain.commands.accounts import ConfirmUser
from src.dbtools.domain.commands.setup import LoadReadModel
from src.dbtools.service_layer.messagebus import MessageBus

# logging
logging.config.dictConfig(LOG_CONFIG)

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

bus: MessageBus = None

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


@app.on_event("startup")
async def startup_event():
    logger = logging.getLogger(__name__)
    logger.debug("Prepare bus")
    bus = await bootstrap.bootstrap()
    #bus = asyncio.create_task(bootstrap.bootstrap())
    # create the schema instance for use in the graphql route
    #  map enums for gql
    affiliation_level = EnumType("AffiliationLevel", AffiliationLevel)
    logger.debug("Prepare graphql schema")
    graphql_query = QueryType()
    graphql_mutation = MutationType()
    graphql_schema = make_executable_schema(
        load_schema_from_path("."),
        graphql_query,
        graphql_mutation,
        snake_case_fallback_resolvers,
        affiliation_level
    )
    logger.debug("Mount graphql")
    app.mount(
        f"/{GQL_API_PATH}",
        GraphQL(
            graphql_schema,
            debug=True,
            logger="src.dbtools.entrypoints.fastapi.graphql"
            # context_value=get_context_value
        )
    )
    logger.debug("Load read model ")
    await bus.handle(LoadReadModel())


@app.on_event("shutdown")
async def shutdown_event():
    logger = logging.getLogger(__name__)
    logger.info("Start shutting down")
    if bus:
        if hasattr(bus.uow, "driver"):
            logger.info("Closing Neo4j driver")
            bus.uow.driver.close()
        logger.info("Closing Redis connection pool")
        await bus.read_model.connection.close()
    logger.info("Finished shutting down")


# todo this is going to be replaced by use of JWT
async def get_user_for_request(request: Request):
    async with bus.uow as uow:
        # consider storing in cookie and
        # just check if cookie is expired
        # refreshing user if needed
        return await uow.accounts.get(request.get('user', ''))


async def get_context_value(request: Request):
    return {
        "request": request,
        "user": await get_user_for_request(request)
    }


@app.get('/')
def read_root():
    logger = logging.getLogger(__name__)
    logger.debug("Hit")
    return RedirectResponse(url=f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}")  # return redirect to front end


@app.get('/confirm')
async def confirm_account(token):
    await bus.handle(ConfirmUser(token=token))
    return RedirectResponse(url='/')
