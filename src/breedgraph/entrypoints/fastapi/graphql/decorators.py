from functools import wraps
from enum import Enum
from pydantic import BaseModel
from inspect import signature
from typing import get_type_hints, get_args, get_origin, Union
from types import UnionType

from breedgraph.custom_exceptions import UnauthorisedOperationError

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

def coerce_value(value, annotation):
    if value is None:
        return None

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[T] / T | None
    if origin in (Union, UnionType):
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return coerce_value(value, non_none[0])

    # list[T] / List[T]
    if origin is list:
        item_type = args[0]
        return [coerce_value(item, item_type) for item in value]

    # primitive types
    if annotation is int:
        return int(value)

    return value

def graphql_payload(func):
    hints = get_type_hints(func)

    @wraps(func)
    async def decorated_function(*args, **kwargs):
        # type coercion here using the registered converters
        for name, annotation in hints.items():
            if name in kwargs:
                kwargs[name] = coerce_value(kwargs[name], annotation)

        errors = []
        try:
            result = await func(*args, **kwargs)
            return {
                "status": GQLStatus.SUCCESS.name if result else GQLStatus.NOT_FOUND.name,
                "result": result
            }
        #except (ServiceUnavailable, NoResultFoundError, IllegalOperationError) as e:
        # todo handle exceptions more gracefully, we probably don't want to expose internal exceptions to the user
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

        user_id = info.context.get("user_id")
        if user_id is None:
            raise UnauthorisedOperationError("Please provide a valid token")

        # Call the original function
        return await func(*args, **kwargs)

    return decorated_function
