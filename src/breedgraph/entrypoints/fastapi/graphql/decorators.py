from functools import wraps
from enum import Enum
from pydantic import BaseModel
from neo4j.exceptions import ServiceUnavailable

from src.breedgraph.custom_exceptions import NoResultFoundError, IllegalOperationError, UnauthorisedOperationError

import logging

logger = logging.getLogger(__name__)
logging.debug("Load decorators")

class GQLStatus(Enum):
    SUCCESS = 1
    NOT_FOUND = 2
    ERROR = 3


class GQLError(BaseModel):
    name: str
    message: str


def graphql_payload(func):
    @wraps(func)

    async def decorated_function(*args, **kwargs):
        errors = []
        try:
            result = await func(*args, **kwargs)
            return {
                "status": GQLStatus.SUCCESS.name if result else GQLStatus.NOT_FOUND.name,
                "result": result
            }
        #except (ServiceUnavailable, NoResultFoundError, IllegalOperationError) as e:
        # todo handle exceptions more gracefully, we don't want to expose internal exceptions to the user
        except Exception as e:
            logging.exception(e)
            errors.append(GQLError(
                name=e.__class__.__name__,
                message=str(e)
            ))
            return {
                "status": GQLStatus.ERROR.name,
                "errors": errors
            }

    return decorated_function


def require_authentication(func):
    """
    Decorator that validates authentication token from cookies and injects user_id into context.
    Raises UnauthorisedOperationError if token is invalid or missing.
    """

    @wraps(func)
    async def decorated_function(*args, **kwargs):
        # Extract info from args (assuming standard GraphQL resolver signature)
        _, info = args[0], args[1]

        # Get token from cookies
        token = info.context["request"].cookies.get("auth_token")

        # Validate token
        user_id = info.context["auth_service"].validate_login_token(token)
        if user_id is None:
            raise UnauthorisedOperationError("Please provide a valid token")

        # Inject user_id into context for use in the resolver
        info.context["user_id"] = user_id

        # Call the original function
        return await func(*args, **kwargs)

    return decorated_function
