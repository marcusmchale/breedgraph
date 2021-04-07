from fastapi import FastAPI, Request
from fastapi.security import OAuth2PasswordBearer
from starlette.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from ariadne.asgi import GraphQL
from src.dbtools.config import PROTOCOL, HOST_ADDRESS, VUE_PORT, GQL_API_PATH
from src.dbtools.domain.commands.accounts import ConfirmUser
from .graphql import graphql_schema  # need to create the bus first (so this is done in init)
from . import bus

import logging

logging.basicConfig(level=logging.DEBUG)


app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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


app.mount(
    f"/{GQL_API_PATH}",
    GraphQL(
        graphql_schema,
        debug=True
        # context_value=get_context_value
    )
)


templates = Jinja2Templates(directory="templates")


@app.get('/')
def read_root():
    return RedirectResponse(url=f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}")  # return redirect to front end


@app.get('/confirm')
async def confirm_account(token):
    await bus.handle(ConfirmUser(token=token))
    return RedirectResponse(url='/')


@app.on_event("shutdown")
def shutdown_event():
    logging.info("Start shutting down")
    if hasattr(bus.uow, "driver"):
        bus.uow.driver.close()
        logging.info("Closed driver")
    logging.info("Finished shutting down")