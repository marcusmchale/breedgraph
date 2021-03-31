from functools import wraps
from neo4j.exceptions import ServiceUnavailable
from dbtools.custom_exceptions import NoResultFoundError, IllegalOperationError
import logging


def graphql_payload(func):
    @wraps(func)
    async def decorated_function(*args, **kwargs):
        errors = []
        try:
            result = await func(*args, **kwargs)
            return {
                'status': True,
                'result': result
            }
        except Exception as e:
            logging.exception(e)
            if isinstance(e, ServiceUnavailable):
                errors.append({
                    "class": e.__class__.__name__,
                    "message": "Database connection failure"
                })
            elif isinstance(e, NoResultFoundError):
                errors.append({
                    "class": e.__class__.__name__,
                    "message": "We couldn't find what you were looking for"
                })
            elif isinstance(e, IllegalOperationError):
                errors.append({
                    "class": e.__class__.__name__,
                    "message": "That operation is not allowed"
                })
            else:
                errors.append({
                    "class": "Unknown",
                    "message": "Something unexpected happened"
                })
            return {
                'status': False,
                'errors': errors
            }

    return decorated_function()
