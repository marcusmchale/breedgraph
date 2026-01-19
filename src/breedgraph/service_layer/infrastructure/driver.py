from abc import ABC, abstractmethod

class AbstractAsyncDriver(ABC):

    @abstractmethod
    def session(self):
        ...

    @abstractmethod
    async def close(self):
        ...