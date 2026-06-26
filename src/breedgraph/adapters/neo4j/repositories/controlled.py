from abc import abstractmethod

from pydantic import BaseModel
from neo4j import AsyncTransaction

from breedgraph.service_layer.tracking import TrackableProtocol
from breedgraph.service_layer.repositories.controlled import (
    ControlledRepository, TControlledAggregate, TAggregateInput, ControlledQueryResult
)
from breedgraph.domain.model.controls import ControlledAggregate

from typing import AsyncGenerator, Generic

import logging
logger = logging.getLogger(__name__)

class Neo4jControlledRepository(
    ControlledRepository[TAggregateInput, TControlledAggregate],
    Generic[TAggregateInput, TControlledAggregate]
):

    def __init__(self, tx: AsyncTransaction, **kwargs):
        super().__init__(**kwargs)
        self.tx = tx

    @abstractmethod
    async def _create_controlled(self, aggregate_input: BaseModel) -> ControlledAggregate:
        raise NotImplementedError

    @abstractmethod
    async def _get_controlled(self, **kwargs) -> ControlledQueryResult[TControlledAggregate]|None:
        raise NotImplementedError

    @abstractmethod
    def _get_all_controlled(self, **kwargs) -> AsyncGenerator[ControlledQueryResult[TControlledAggregate], None]:
        raise NotImplementedError

    @abstractmethod
    async def _remove_controlled(self, aggregate: ControlledAggregate):
        raise NotImplementedError

    @abstractmethod
    async def _update_controlled(self, aggregate: ControlledAggregate | TrackableProtocol):
        raise NotImplementedError