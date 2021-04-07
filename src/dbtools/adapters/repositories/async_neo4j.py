# this is to use while waiting for a proper implementation of async for neo4j bolt driver for python
# it is just farming out the awaits to a thread pool to prevent locking of the main thread
# https://github.com/neo4j/neo4j-python-driver/issues/180
from abc import abstractmethod
from types import TracebackType
from typing import Awaitable, Type, Union, Optional, overload

from neo4j import Transaction, Result, Record
from asyncio import AbstractEventLoop
from collections.abc import AsyncGenerator


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

    def __init__(self, tx: Transaction, loop: AbstractEventLoop):
        self.tx = tx
        self.loop = loop

    def _run(self, query: str, parameters: dict):
        return self.tx.run(query, parameters)

    async def run(self, query: str, **parameters) -> Result:
        return await self.loop.run_in_executor(None, self._run, query, parameters)

    async def single(self, query: str, **parameters) -> Record:
        result = await self.run(query, **parameters)
        return await self.loop.run_in_executor(None, result.single)

    async def records(self, query: str, **parameters) -> AsyncGenerator[Record, None]:

        result = AsyncResult(await self.run(query, **parameters))

        async for record in result:
            yield record













