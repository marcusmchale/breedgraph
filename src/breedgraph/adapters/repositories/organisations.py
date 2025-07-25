import logging

from abc import ABC, abstractmethod
from neo4j import AsyncTransaction, AsyncResult, Record

from src.breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

from src.breedgraph.domain.model.organisations import (
    TeamInput,
    TeamStored,
    Organisation,
    Access,
    Affiliation,
    Affiliations
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList, TrackedDict, TrackedGraph
from src.breedgraph.adapters.repositories.base import BaseRepository

from typing import AsyncGenerator, Set, Dict

logger = logging.getLogger(__name__)

class Neo4jOrganisationsRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction, user_id: int|None = None, redacted: bool = True):
        super().__init__()
        self.user_id: int|None = user_id
        self.tx = tx
        self.redacted = redacted

    async def _create(self, team: TeamInput, *args) -> Organisation:
        team = await self._create_team(team, admin_heritable = True)
        org = Organisation(nodes=[team])
        if self.redacted:
            return org.redacted(self.user_id)
        else:
            return org

    async def _create_team(self, team: TeamInput, admin_heritable: bool = False) -> TeamStored:
        if self.user_id is None:
            raise UnauthorisedOperationError("User ID required to create a team")

        logger.debug(f"Create team: {team}")
        result: AsyncResult = await self.tx.run(
            queries['organisations']['create_team'],
            name=team.name,
            name_lower=team.name.casefold(),
            fullname=team.fullname,
            admin=self.user_id,
            heritable=admin_heritable
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
        for access in team.affiliations.changed:
            access = Access(access.upper())
            for user_id in team.affiliations.get_by_access(access).added.union(team.affiliations.get_by_access(access).changed):
                affiliation = team.affiliations.get_by_access(access)[user_id]
                await self.tx.run(
                    queries['affiliations'][f'set_{access.casefold()}'],
                    user=user_id,
                    team=team.id,
                    authorisation=affiliation.authorisation,
                    heritable=affiliation.heritable
                )
            for user_id in team.affiliations.get_by_access(access).removed:
                await self.tx.run(
                    queries['affiliations'][f'remove_{access.casefold()}'],
                    user=user_id,
                    team=team.id
                )

    async def _delete_team(self, team_id: int):
        await self.tx.run(
            queries['organisations']['delete_team'],
            team=team_id
        )

    async def _get(self, team_id=None) -> Organisation|None:
        if team_id is None:
            try:
                return await anext(self._get_all())
            except StopAsyncIteration:
                return None

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

        if not nodes:
            return None

        org = Organisation(nodes=nodes, edges=edges)
        if self.redacted:
            return org.redacted(self.user_id)
        else:
            return org


    async def _get_all(self) -> AsyncGenerator[Organisation, None]:
        result: AsyncResult = await self.tx.run(
            queries['organisations']['get_organisations']
        )
        async for record in result:
            teams = [self.team_record_to_team(team) for team in record['organisation']]
            edges = [edge for team in record['organisation'] for edge in team.get('includes', [])]
            org = Organisation(nodes=teams, edges=edges)

            if self.redacted:
                yield org.redacted(self.user_id)
            else:
                yield org

    async def _remove(self, organisation: Organisation):
        for team_id in organisation.teams.keys():
            await self._delete_team(team_id)

    async def _update(self, organisation: Tracked|Organisation):
        if not organisation.changed:
            return

        for node_id in organisation._graph.added_nodes:
            team = organisation.get_team(node_id)
            if isinstance(team, TeamInput):
                stored_team = await self._create_team(team)
                organisation._graph.replace_with_stored(node_id, stored_team)

            elif isinstance(team, TeamStored):
                pass
            else:
                raise ValueError("Only TeamInput and TeamStored may be added to organisation")

        for node_id in organisation._graph.removed_nodes:
            await self._delete_team(node_id)

        for node_id in organisation._graph.changed_nodes:
            team = organisation.get_team(node_id)
            if not isinstance(team, TeamStored):
                raise ValueError("Can only commit changes to stored teams")
            await self._set_team(team)

        await self._create_edges(organisation._graph.added_edges)
        await self._delete_edges(organisation._graph.removed_edges)

    async def _create_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['organisations']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['organisations']['delete_edges'], edges=list(edges))

    @staticmethod
    def team_record_to_team(record) -> TeamStored:
        affiliations = Affiliations()
        for key, value in record['affiliations'].items():
            record['affiliations'][Access[key]] = {v['id']: Affiliation(authorisation = v['authorisation'], heritable = v['heritable']) for v in value}
        for access in record['affiliations'].keys():
            for user_id in record['affiliations'][access]:
                affiliations.set_by_access(Access(access), user_id, record['affiliations'][access][user_id])
        record['affiliations'] = affiliations
        return TeamStored(**record)


