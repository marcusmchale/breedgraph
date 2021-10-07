# this is to use while waiting for a proper implementation of async for neo4j bolt driver for python
# it is just farming out the awaits to a thread pool to prevent locking of the main thread
# https://github.com/neo4j/neo4j-python-driver/issues/180
from abc import abstractmethod
from types import TracebackType
from typing import Awaitable, Type, Union, Optional, overload


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from concurrent.futures import ThreadPoolExecutor
    from neo4j import Transaction, Result, Record
    from asyncio import AbstractEventLoop
    from collections.abc import AsyncGenerator

import logging

logger = logging.getLogger(__name__)


class AsyncResult:

    def __init__(self, result):
        self.result = iter(result)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.result)
        except StopIteration:
            raise StopAsyncIteration


class AsyncNeo4j:

    def __init__(self, tx: "Transaction", loop: "AbstractEventLoop", thread_pool: "ThreadPoolExecutor"):
        self.tx = tx
        self.loop = loop
        self.thread_pool = thread_pool

    def _run(self, query: str, parameters: dict):
        logger.info(f"Running query: {query} \n parameters: {parameters}")
        return self.tx.run(query, parameters)

    async def run(self, query: str, **parameters) -> "Result":
        logger.debug("Running in thread pool")
        return await self.loop.run_in_executor(self.thread_pool, self._run, query, parameters)

    async def single(self, query: str, **parameters) -> "Record":
        logger.debug("Returning single record")
        result: "Result" = await self.run(query, **parameters)
        return await self.loop.run_in_executor(self.thread_pool, result.single)

    async def records(self, query: str, **parameters) -> "AsyncGenerator[Record, None]":
        logger.debug("Returning async generator of records")
        result = AsyncResult(await self.run(query, **parameters))

        async for record in result:
            yield record
