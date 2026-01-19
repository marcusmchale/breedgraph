import pytest_asyncio
from itsdangerous import URLSafeTimedSerializer

from src.breedgraph.config import LOGIN_SALT, SECRET_KEY

@pytest_asyncio.fixture(scope="session")
async def system_user_login_token() -> str:
    return URLSafeTimedSerializer(SECRET_KEY).dumps(1,salt=LOGIN_SALT)

@pytest_asyncio.fixture(scope="session")
async def first_user_login_token(first_account) -> str:
    return URLSafeTimedSerializer(SECRET_KEY).dumps(first_account.user.id,salt=LOGIN_SALT)

@pytest_asyncio.fixture(scope="session")
async def second_user_login_token(second_account) -> str:
    return URLSafeTimedSerializer(SECRET_KEY).dumps(second_account.user.id, salt=LOGIN_SALT)
