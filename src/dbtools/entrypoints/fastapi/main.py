from fastapi import FastAPI, Request
from fastapi.security import OAuth2PasswordBearer
from starlette.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from ariadne.asgi import GraphQL
from src.dbtools.config import (
    PROTOCOL,
    HOST_ADDRESS,
    VUE_PORT,
    GQL_API_PATH,
    LOG_CONFIG
)

import logging.config

from src.dbtools import bootstrap
from src.dbtools.domain.commands.accounts import ConfirmUser
from src.dbtools.domain.commands.setup import LoadReadModel

bus = bootstrap.bootstrap()

from .graphql import graphql_schema  # need to create the bus first


# logging
logging.config.dictConfig(LOG_CONFIG)

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
    return RedirectResponse(url=f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}")  # return redirect to front end


@app.get('/confirm')
async def confirm_account(token):
    await bus.handle(ConfirmUser(token=token))
    return RedirectResponse(url='/')


@app.on_event("startup")
async def startup_event():
    logger = logging.getLogger(__name__)
    logger.info("Start FastAPI")
    app.mount(
        f"/{GQL_API_PATH}",
        GraphQL(
            graphql_schema,
            debug=True,
            logger="src.dbtools.entrypoints.fastapi.graphql"
            # context_value=get_context_value
        )
    )
    bus.read_model.create()
    await bus.handle(LoadReadModel())





@app.on_event("shutdown")
async def shutdown_event():
    logger = logging.getLogger(__name__)
    logger.info("Start shutting down")
    if hasattr(bus.uow, "driver"):
        logger.info("Closing Neo4j driver")
        bus.uow.driver.close()
    logger.info("Closing Redis connection pool")
    bus.read_model.redis.close()
    bus.thread_pool.shutdown()
    logger.info("Finished shutting down")
