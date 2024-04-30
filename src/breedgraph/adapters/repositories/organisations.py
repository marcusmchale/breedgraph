import logging

from abc import ABC, abstractmethod
from neo4j import AsyncTransaction, AsyncResult, Record

from src.breedgraph.domain.model.organisations import (
    TeamInput,
    TeamStored,
    OrganisationInput,
    OrganisationStored
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.custom_exceptions import ProtectedNodeError, IllegalOperationError


from typing import Set, AsyncGenerator

logger = logging.getLogger(__name__)

class BaseOrganisationRepository(ABC):

    def __init__(self):
        self.seen: Set[OrganisationStored] = set()

    def _track(self, organisation: OrganisationStored):
        organisation.teams = TrackedList(organisation.teams)
        self.seen.add(organisation)

    async def create(self, organisation: OrganisationInput) -> OrganisationStored:
        organisation_stored = await self._create(organisation)
        self._track(organisation_stored)
        return organisation_stored

    @abstractmethod
    async def _create(self, organisation: OrganisationInput) -> OrganisationStored:
        raise NotImplementedError

    async def get(self, team_id: int) -> OrganisationStored:
        organisation = await self._get(team_id)
        if organisation is not None:
            self._track(organisation)
        return organisation

    @abstractmethod
    async def _get(self, team_id: int) -> OrganisationStored:
        raise NotImplementedError

    async def get_all(self) -> AsyncGenerator[OrganisationStored, None]:
        async for organisation in self._get_all():
            self._track(organisation)
            yield organisation

    @abstractmethod
    def _get_all(self) -> AsyncGenerator[OrganisationStored, None]:
        raise NotImplementedError

    async def remove(self, organisation: OrganisationStored):
        if organisation.root.children:
            raise ProtectedNodeError

        await self._remove(organisation)

    @abstractmethod
    async def _remove(self, organisation: OrganisationStored):
        raise NotImplementedError

    async def update_seen(self):
        for organisation in self.seen:
            await self._update(organisation)
        self.seen.clear()

    @abstractmethod
    async def _update(self, organisation: OrganisationStored):
        raise NotImplementedError


class Neo4jOrganisationRepository(BaseOrganisationRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, organisation: OrganisationInput) -> OrganisationStored:
        for team in organisation.teams:
            stored_team: TeamStored = await self._create_team(team)
            return OrganisationStored(teams=[stored_team])

    async def _get(self, team: int) -> OrganisationStored:
        result: AsyncResult = await self.tx.run(
            queries['get_organisation'],
            team=team
        )
        teams = list()
        async for record in result:
            teams.append(self.team_record_to_team(record['team']))

        return OrganisationStored(teams=teams)

    async def _get_all(self) -> AsyncGenerator[OrganisationStored, None]:
        result: AsyncResult = await self.tx.run(
            queries['get_organisations']
        )
        async for record in result:
            yield OrganisationStored(teams = record['teams'])

    async def _create_team(self, team: TeamInput):
        logger.debug(f"Create team: {team}")

        if team.parent is not None:
            result: AsyncResult = await self.tx.run(
                queries['create_team_with_parent'],
                name=team.name,
                name_lower=team.name.casefold(),
                fullname=team.fullname,
                parent=team.parent
            )
        else:
            result: AsyncResult = await self.tx.run(
                queries['create_team'],
                name=team.name,
                name_lower=team.name.casefold(),
                fullname=team.fullname
            )

        record: Record = await result.single()
        return self.team_record_to_team(record['team'])

    async def _set_team(self, team: TeamStored):
        logger.debug(f"Set team: {team}")
        # todo test if parent_id has changed, if so need to update parent also (its children have changed)
        if team.parent is not None:
            await self.tx.run(
                queries['set_team_with_parent_id'],
                team=team.id,
                parent=team.parent,
                name=team.name,
                name_lower=team.name.casefold(),
                fullname=team.fullname
            )
        else:
            await self.tx.run(
                queries['set_team'],
                team=team.id,
                name=team.name,
                name_lower=team.name.casefold(),
                fullname=team.fullname
            )

    async def _remove(self, organisation: OrganisationStored):
        for team in organisation.teams:
            await self._remove_team(team)

    async def _remove_team(self, team: TeamStored):
        await self.tx.run(
            queries['remove_team'],
            team_id=team.id
        )

    async def _update(self, organisation: OrganisationStored):
        if not isinstance(organisation.teams, Tracked):
            raise IllegalOperationError("Organisation changes must be tracked for neo4j updates")

        if not organisation.teams.changed:
            return

        for team in organisation.teams:
            if team.changed or team in organisation.teams.added:
                if isinstance(team, TeamStored):
                    await self._set_team(team)
                else:
                    await self._create_team(team)


        for team in organisation.teams.removed:
            await self._remove_team(team)

    @staticmethod
    def team_record_to_team(record) -> TeamStored:
        return TeamStored(
            name=record['name'],
            fullname=record['fullname'],
            id=record['id'],
            parent=record['parent'],
            children=record['children'],
            readers=record['readers'],
            writers=record['writers'],
            admins=record['admins'],
            requests=record['requests']
        )
