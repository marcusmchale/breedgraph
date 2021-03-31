# this is to use while waiting for a proper implementation of async for neo4j bolt driver for python
# it is just farming out the awaits to a thread pool to prevent locking of the main thread
# https://github.com/neo4j/neo4j-python-driver/issues/180

from neo4j import Transaction, Result, Record
from asyncio import AbstractEventLoop
from typing import AsyncGenerator


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

    async def records(self, query: str, **parameters) -> AsyncGenerator[Record]:
        result = await self.run(query, **parameters)
        iter_result = iter(result)
        while True:
            yield await self.loop.run_in_executor(None, next, iter_result)






