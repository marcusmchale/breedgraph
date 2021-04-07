import logging
from functools import wraps
from enum import Enum
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from neo4j.exceptions import ServiceUnavailable
from dbtools.custom_exceptions import NoResultFoundError, IllegalOperationError


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
            return jsonable_encoder({
                "status": GQLStatus.SUCCESS if result else GQLStatus.NOT_FOUND,
                "result": result
            })
        except (ServiceUnavailable, NoResultFoundError, IllegalOperationError) as e:
            logging.exception(e)
            errors.append(GQLError(
                name=e.__class__.__name__,
                message=str(e)
            ))
            return jsonable_encoder({
                "status": GQLStatus.ERROR,
                "errors": errors
            })
        except Exception as e:
            logging.exception(e)
            errors.append(GQLError(
                name="Other",
                message="Something unexpected happened"
            ))
            return jsonable_encoder({
                "status": GQLStatus.ERROR,
                "errors": errors
            })
    return decorated_function()
