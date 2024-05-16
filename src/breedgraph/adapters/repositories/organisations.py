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
from src.breedgraph.adapters.repositories.base import BaseRepository

from typing import Any, AsyncGenerator, List

logger = logging.getLogger(__name__)

class Neo4jOrganisationRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, organisation: OrganisationInput) -> OrganisationStored:
        teams = [await self._create_team(team) for team in organisation.teams]
        return OrganisationStored(teams=teams)

    async def _create_team(self, team: TeamInput):
        logger.debug(f"Create team: {team}")
        if team.parent is not None:
            result: AsyncResult = await self.tx.run(
                queries['organisations']['create_team_with_parent'],
                name=team.name,
                name_lower=team.name.casefold(),
                fullname=team.fullname,
                parent=team.parent
            )
        else:
            result: AsyncResult = await self.tx.run(
                queries['organisations']['create_team'],
                name=team.name,
                name_lower=team.name.casefold(),
                fullname=team.fullname
            )

        record: Record = await result.single()
        return self.team_record_to_team(record['team'])

    async def _get(self, team_id=None) -> OrganisationStored:
        if team_id is None:
            raise TypeError(f"Get organisation requires team_id")

        result: AsyncResult = await self.tx.run(
            queries['organisations']['get_organisation'],
            team=team_id
        )

        teams = [self.team_record_to_team(record['team']) async for record in result]
        return OrganisationStored(teams=teams)

    async def _get_all(self) -> AsyncGenerator[OrganisationStored, None]:
        result: AsyncResult = await self.tx.run(
            queries['organisations']['get_organisations']
        )
        async for record in result:
            yield OrganisationStored(teams = record['teams'])

    async def _set_team(self, team: TeamStored):
        logger.debug(f"Set team: {team}")
        await self.tx.run(
            queries['organisations']['set_team'],
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
            queries['organisations']['remove_team'],
            team=team.id
        )

    async def _update(self, organisation: OrganisationStored|Tracked):
        if not organisation.changed:
            return

        await self._update_teams(organisation.teams)

    async def _update_teams(self, teams: List|TrackedList):
        for i in teams.added:
            teams[i] = await self._create_team(teams[i])

        for i in teams.changed:
            await self._set_team(teams[i])

        for team in teams.removed:
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
            read_requests=record['read_requests'],
            write_requests=record['write_requests'],
            admin_requests=record['admin_requests']
        )
