import logging

from abc import ABC, abstractmethod
from neo4j import AsyncTransaction, AsyncResult, Record

from src.breedgraph.domain.model.organisations import (
    TeamInput,
    TeamStored,
    Organisation
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList, TrackedDict
from src.breedgraph.adapters.repositories.base import BaseRepository

from typing import AsyncGenerator, List, Dict

logger = logging.getLogger(__name__)

class Neo4jOrganisationRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, team: TeamInput) -> Organisation:
        team = await self._create_team(team)
        return Organisation(root_id=team.id, teams={team.id: team})

    async def _create_team(self, team: TeamInput) -> TeamStored:
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

    async def _get(self, team_id=None) -> Organisation:
        if team_id is None:
            raise TypeError(f"Get organisation requires team_id")

        result: AsyncResult = await self.tx.run(
            queries['organisations']['get_organisation'],
            team=team_id
        )

        teams = [self.team_record_to_team(record['team']) async for record in result]
        return Organisation.from_list(teams)

    async def _get_all(self) -> AsyncGenerator[Organisation, None]:
        result: AsyncResult = await self.tx.run(
            queries['organisations']['get_organisations']
        )
        async for record in result:
            teams = [self.team_record_to_team(team) for team in record['teams']]
            yield Organisation.from_list(teams)

    async def _set_team(self, team: TeamStored):
        logger.debug(f"Set team: {team}")
        await self.tx.run(
            queries['organisations']['set_team'],
            team=team.id,
            name=team.name,
            name_lower=team.name.casefold(),
            fullname=team.fullname
        )

    async def _remove(self, organisation: Organisation):
        for team_id in organisation.teams.keys():
            await self._remove_team(team_id)

    async def _remove_team(self, team_id: int):
        await self.tx.run(
            queries['organisations']['remove_team'],
            team=team_id
        )

    async def _update(self, organisation: Tracked|Organisation):
        if not organisation.changed:
            return

        await self._update_teams(organisation.teams)

    async def _update_teams(self, teams: TrackedDict[int, Tracked|TeamInput|TeamStored]):
        await self._create_teams(teams)
        await self._remove_teams(teams)
        await self._update_changed_teams(teams)

    async def _create_teams(self,teams: TrackedDict[int, Tracked|TeamInput|TeamStored]):
        for team_id in teams.added:
            team = teams[team_id]
            if isinstance(team, TeamInput):
                stored_team = await self._create_team(team)
                teams.silent_set(stored_team.id, stored_team)
                teams.silent_remove(team_id)
            else:
                raise ValueError("An instance of TeamInput is required for team creation")

    async def _remove_teams(self, teams: TrackedDict[int, Tracked|TeamInput|TeamStored]):
        for team_id in teams.removed.keys():
            await self._remove_team(team_id)

    async def _update_changed_teams(self, teams: TrackedDict[int, Tracked|TeamInput|TeamStored]):
        for team_id in teams.changed:
            team = teams[team_id]
            await self._set_team(team)

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
