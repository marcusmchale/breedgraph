from abc import ABC, abstractmethod

from pydantic import BaseModel

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.adapters.repositories.base import BaseRepository

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.base import Aggregate
from src.breedgraph.domain.model.controls import Release, Control, WriteStamp, RecordController

from typing import List, Tuple, AsyncGenerator

import logging

logger = logging.getLogger(__name__)

class ControlledRepository(BaseRepository, ABC):

    def __init__(self, account: AccountStored):
        super().__init__()
        self.account: AccountStored = account
        self.writes_for = self.account.writes if self.account else []

    def set_writes_for(self, writes: List[int]):
        self.writes_for = [i for i in writes if i in self.account.writes]
        if not self.writes_for:
            logger.debug("Setting writes to empty list")

    async def _create(
            self,
            aggregate_input: BaseModel
    ) -> Aggregate:
        if self.account is None:
            raise ValueError("Only registered accounts may create controlled records")

        elif not self.writes_for: 
            raise UnauthorisedOperationError(f"Account does not have a stored write affiliation: {self.account.user.id}")

        return await self._create_controlled(aggregate_input)

    @abstractmethod
    async def _create_controlled(self, aggregate_input: BaseModel) -> Aggregate:
        raise NotImplementedError

    async def _get(self, **kwargs):
        aggregate, controller = await self._get_controlled(**kwargs)
        if controller.can_read(self.account):
            return aggregate
        else:
            raise UnauthorisedOperationError("Account cannot access this aggregate")

    async def _get_controlled(self, **kwargs) -> Tuple[Aggregate, RecordController]:
        raise NotImplementedError

    async def _get_all(self, **kwargs) -> AsyncGenerator[Aggregate, None]:
        async for aggregate, controller in self._get_all_controlled():
            if controller.can_read(self.account):
                yield aggregate

    @abstractmethod
    def _get_all_controlled(self) -> AsyncGenerator[Tuple[Aggregate, RecordController], None]:
        raise NotImplementedError

    @abstractmethod
    async def _get_controller(self, aggregate: Aggregate) -> RecordController:
        raise NotImplementedError

    async def _remove(self, aggregate: Aggregate):
        controller = await self._get_controller(aggregate)
        if controller.can_curate(self.account):
            await self._remove_controlled(aggregate)

    @abstractmethod
    async def _remove_controlled(self, aggregate: Aggregate):
        raise NotImplementedError

    async def _update(self, aggregate: Aggregate|Tracked):
        controller = await self._get_controller(aggregate)
        if not aggregate.changed:
            return
        if controller.can_curate(self.account):
            await self._update_controlled(aggregate)

    @abstractmethod
    async def _update_controlled(self, aggregate: Aggregate|Tracked):
        raise NotImplementedError

    async def set_release(self, aggregate: Aggregate, release: Release):
        controller = await self._get_controller(aggregate)
        if controller.can_release(self.account):
            await self._set_release(aggregate, release)
        else:
            raise ValueError("Only admins for a record controller can change release")

    @abstractmethod
    async def _set_release(self, aggregate, release):
        raise NotImplementedError

    async def add_control(self, aggregate: Aggregate, team: int):
        controller = await self._get_controller(aggregate)
        if controller.can_release(self.account):
            await self._add_control(aggregate, team, controller.release)
        else:
            raise UnauthorisedOperationError("Only admins for a record controller can add more controls")

    @abstractmethod
    async def _add_control(self, aggregate:Aggregate, team: int, release: Release):
        raise NotImplementedError

    async def remove_control(self, aggregate: Aggregate, team: int):
        if team in self.account.admins:
            controller = await self._get_controller(aggregate)
            if len(controller.controls) == 1:
                raise ValueError("The last controller for a record can not be removed")
            await self._remove_control(aggregate, team)
        else:
            raise UnauthorisedOperationError("Control can only be removed by admins for the given team")

    @abstractmethod
    async def _remove_control(self, aggregate:Aggregate, team: int):
        raise NotImplementedError

    @staticmethod
    def record_to_controller(record):
        return RecordController(
            controls=[
                Control(
                    time=c['time'].to_native(),
                    team=c['team'],
                    release=c['release']
                )
                for c in record['controls']
            ],
            writes=[
                WriteStamp(
                    time=w['time'].to_native(),
                    user=w['user']
                ) for w in record['writes']
            ]
        )


