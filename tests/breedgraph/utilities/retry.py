import asyncio
from .exceptions import TooManyRetries

def retry(attempts):
    def func_wrapper(f):
        async def wrapper(*args, **kwargs):
            for attempt in range(attempts):
                result = await f(*args, **kwargs)
                if result is not None:
                    return result
                else:
                    await asyncio.sleep(1)
            raise TooManyRetries
        return wrapper
    return func_wrapper
