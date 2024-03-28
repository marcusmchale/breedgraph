from functools import wraps
from enum import Enum
from pydantic import BaseModel
from neo4j.exceptions import ServiceUnavailable
from src.breedgraph.custom_exceptions import NoResultFoundError, IllegalOperationError

import logging

logger = logging.getLogger(__name__)
logging.debug("Load graphql decorators")

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
        except (ServiceUnavailable, NoResultFoundError, IllegalOperationError) as e:
            logging.exception(e)
            errors.append(GQLError(
                name=e.__class__.__name__,
                message=str(e)
            ))
            return {
                "status": GQLStatus.ERROR.name,
                "errors": errors
            }
        except Exception as e:
            logging.exception(e)
            errors.append(GQLError(
                name="Other",
                message="Something unexpected happened"
            ))
            return {
                "status": GQLStatus.ERROR.name,
                "errors": errors
            }
    return decorated_function
