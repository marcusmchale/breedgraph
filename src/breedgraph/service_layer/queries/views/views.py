from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, AbstractAsyncContextManager

from src.breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from src.breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver

from .accounts import AbstractAccountsView
from .regions import AbstractRegionsView
from .datasets import AbstractDatasetsView

from typing import AsyncGenerator

import logging
logger = logging.getLogger(__name__)

class AbstractViewsHolder(ABC):
    accounts: AbstractAccountsView
    regions: AbstractRegionsView
    datasets: AbstractDatasetsView


class AbstractViewsFactory(ABC):

    def __init__(self, driver: AbstractAsyncDriver, state_store: AbstractStateStore):
        self.driver = driver
        self.state_store = state_store

    @asynccontextmanager
    async def get_views(
            self,
            user_id: int = None
    ) -> AsyncGenerator[AbstractViewsHolder, None]:
        async with self._get_views(user_id=user_id) as views:
            try:
                yield views
            except Exception as e:
                logger.error(f"Error in views: {e}")
                raise e

    @abstractmethod
    def _get_views(self, user_id: int = None) -> AbstractAsyncContextManager[AbstractViewsHolder, None]:
        ...