import logging

from abc import ABC, abstractmethod
from neo4j import AsyncTransaction, AsyncResult, Record

from src.breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.organisations import (
    TeamInput,
    TeamStored,
    Organisation,
    Access,
    Authorisation,
    Affiliation
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList, TrackedDict, TrackedGraph
from src.breedgraph.adapters.repositories.base import BaseRepository

from typing import AsyncGenerator, List, Dict

logger = logging.getLogger(__name__)

class Neo4jOrganisationRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction, account:AccountStored = None):
        super().__init__()
        self.account: AccountStored = account
        self.tx = tx

    async def _create(self, team: TeamInput, *args) -> Organisation:
        team = await self._create_team(team)
        return Organisation(nodes=[team])

    async def _create_team(self, team: TeamInput) -> TeamStored:
        if self.account is None:
            raise UnauthorisedOperationError("Account required to create a team")

        logger.debug(f"Create team: {team}")
        result: AsyncResult = await self.tx.run(
            queries['organisations']['create_team'],
            name=team.name,
            name_lower=team.name.casefold(),
            fullname=team.fullname,
            admin=self.account.user.id
        )
        record: Record = await result.single()
        return self.team_record_to_team(record['team'])

    async def _set_team(self, team: TeamStored|Tracked):
        logger.debug(f"Set team: {team}")
        await self.tx.run(
            queries['organisations']['set_team'],
            team=team.id,
            name=team.name,
            name_lower=team.name.casefold(),
            fullname=team.fullname
        )
        await self._set_team_access(team)

    async def _set_team_access(self, team: TeamStored|Tracked):
        for access in team.affiliations.changed.union(team.affiliations.added):
            for user_id in team.affiliations[access].added.union(team.affiliations[access].changed):
                affiliation = team.affiliations[access][user_id]
                await self.tx.run(
                    queries['affiliations'][f'set_{access.casefold()}'],
                    user=user_id,
                    team=team.id,
                    authorisation=affiliation.authorisation,
                    heritable=affiliation.heritable
                )
            for user_id in team.affiliations[access].removed:
                await self.tx.run(
                    queries['affiliations'][f'remove_{access.casefold()}'],
                    user=user_id,
                    team=team.id
                )

    async def _remove_team(self, team_id: int):
        await self.tx.run(
            queries['organisations']['remove_team'],
            team=team_id
        )

    async def _get(self, team_id=None) -> Organisation:
        if team_id is None:
            raise ValueError(f"Get organisation requires team_id")

        result: AsyncResult = await self.tx.run(
            queries['organisations']['get_organisation'],
            team=team_id
        )

        nodes = []
        edges = []

        async for record in result:
            team = self.team_record_to_team(record['team'])
            nodes.append(team)
            for edge in record.get('includes', []):
                edges.append(edge)

        return Organisation(nodes=nodes, edges=edges)

    async def _get_all(self) -> AsyncGenerator[Organisation, None]:
        result: AsyncResult = await self.tx.run(
            queries['organisations']['get_organisations']
        )
        async for record in result:
            teams = [self.team_record_to_team(team) for team in record['organisation']]
            edges = [edge for team in record['organisation'] for edge in team.get('includes', [])]
            yield Organisation(nodes=teams, edges=edges)

    async def _remove(self, organisation: Organisation):
        for team_id in organisation.teams.keys():
            await self._remove_team(team_id)

    async def _update(self, organisation: Tracked|Organisation):
        if not organisation.changed:
            return

        for node_id in organisation.graph.added_nodes:
            team = organisation.get_team(node_id)
            if isinstance(team, TeamInput):
                stored_team = await self._create_team(team)
                organisation.graph.replace_with_stored(node_id, stored_team)
            elif isinstance(team, TeamStored):
                pass
            else:
                raise ValueError("Only TeamInput and TeamStored may be added to organisation")

        for node_id in organisation.graph.removed_nodes:
            await self._remove_team(node_id)

        for node_id in organisation.graph.changed_nodes:
            team = organisation.get_team(node_id)
            if not isinstance(team, TeamStored):
                raise ValueError("Can only commit changes to stored teams")
            await self._set_team(team)

        await self. _create_edges(list(organisation.graph.added_edges))
        await self._remove_edges(list(organisation.graph.removed_edges))

    async def _create_edges(self, edges: List[tuple[int, int]]):
        await self.tx.run(queries['organisations']['create_edges'], edges=edges)

    async def _remove_edges(self, edges: List[tuple[int, int]]):
        await self.tx.run(queries['organisations']['remove_edges'], edges=edges)

    @staticmethod
    def team_record_to_team(record) -> TeamStored:
        for key, value in record['affiliations'].items():
            record['affiliations'][Access[key]] = {v['id']: Affiliation(authorisation = v['authorisation'], heritable = v['heritable']) for v in value}
        return TeamStored(**record)

