from fastapi import FastAPI, Request
from fastapi.security import OAuth2PasswordBearer
from starlette.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from ariadne.asgi import GraphQL

from dbtools.domain.commands.accounts import ConfirmUser

from .graphql import graphql_schema  # need to create the bus first (so this is done in init)
from . import bus

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

origins = [
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_user_for_request(request: Request):
    with bus.uow as uow:
        # consider storing in cookie and
        # just check if cookie is expired
        # refreshing user if needed
        return await uow.accounts.get(request.get('user', ''))


async def get_context_value(request: Request):
    return {
        "request": request,
        "user": await get_user_for_request(request)
    }


app.mount("/graphql", GraphQL(graphql_schema, debug=True, context_value=get_context_value))

templates = Jinja2Templates(directory="templates")


@app.get('/')
def read_root(request: Request):
    return RedirectResponse(url="http://" + request.client.host + ":8080")  # return redirect to front end


@app.get('/confirm')
async def confirm_account(token):
    await bus.handle(ConfirmUser(token=token))
    return RedirectResponse(url='/')
