import logging

from neo4j import AsyncTransaction, AsyncResult, Record

from breedgraph.custom_exceptions import UnauthorisedOperationError
from breedgraph.domain.model.team_trees import (
    TeamInput,
    TeamStored,
    TeamTree,
    Affiliation,
    Affiliations,
    Authorisation
)
from breedgraph.domain.model.controls import Access
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.tracking import TrackableProtocol
from breedgraph.service_layer.repositories.base import BaseRepository

from typing import AsyncGenerator, Set, List

logger = logging.getLogger(__name__)


class Neo4jTeamTreesRepository(BaseRepository[TeamInput, TeamTree]):
    """
    Returns whole team trees, so that writes see every team and affiliation.
    Reads that show a team tree to a user must redact it for them with TeamTree.redacted.
    """

    def __init__(self, tx: AsyncTransaction, user_id: int|None = None):
        super().__init__()
        self.user_id: int|None = user_id
        self.tx = tx

    async def _create(self, team: TeamInput, *args) -> TeamTree:
        team = await self._create_team(team, admin_heritable = True)
        return TeamTree(nodes=[team])

    async def _create_team(self, team: TeamInput, admin_heritable: bool = False) -> TeamStored:
        if self.user_id is None:
            raise UnauthorisedOperationError("User ID required to create a team")

        logger.debug(f"Create team: {team}")
        result: AsyncResult = await self.tx.run(
            queries['team_trees']['create_team'],
            name=team.name,
            name_lower=team.name.casefold(),
            fullname=team.fullname,
            admin=self.user_id,
            heritable=admin_heritable
        )
        record: Record = await result.single()
        return self.team_record_to_team(record['team'])

    async def _set_team(self, team: TeamStored|TrackableProtocol):
        logger.debug(f"Set team: {team}")
        await self.tx.run(
            queries['team_trees']['set_team'],
            team=team.id,
            name=team.name,
            name_lower=team.name.casefold(),
            fullname=team.fullname
        )
        await self._set_team_access(team)

    async def _set_team_access(self, team: TeamStored|TrackableProtocol):
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
            queries['team_trees']['delete_team'],
            team=team_id,
            user_id=self.user_id
        )

    async def _get(self, team_id=None) -> TeamTree|None:
        if team_id is None:
            try:
                return await anext(self._get_all())
            except StopAsyncIteration:
                return None

        result: AsyncResult = await self.tx.run(
            queries['team_trees']['get_team_tree'],
            team=team_id
        )

        nodes = []
        edges = []

        async for record in result:
            record_data = dict(record)
            for edge in record_data.pop('includes'):
                edges.append(edge)
            team = self.team_record_to_team(record_data['team'])
            nodes.append(team)

        if not nodes:
            return None

        return TeamTree(nodes=nodes, edges=edges)

    async def _get_all(self, team_ids: List[int] | Set[int] | None = None) -> AsyncGenerator[TeamTree, None]:
        if team_ids is None:
            result: AsyncResult = await self.tx.run(
                queries['team_trees']['get_team_trees']
            )
        else:
            if isinstance(team_ids, set):
                team_ids = list(team_ids)
            result: AsyncResult = await self.tx.run(
                queries['team_trees']['get_team_trees_by_team'],
                team_ids=team_ids
            )
        async for record in result:
            edges = [edge for team in record['team_tree'] for edge in team.pop('includes')]
            teams = [self.team_record_to_team(team) for team in record['team_tree']]
            yield TeamTree(nodes=teams, edges=edges)

    async def _remove(self, team_tree: TeamTree):
        for team_id in team_tree.teams.keys():
            await self._delete_team(team_id)

    async def _update(self, team_tree: TrackableProtocol|TeamTree):
        if not team_tree.changed:
            return

        for node_id in team_tree._graph.added_nodes:
            team = team_tree.get_team(node_id)
            if isinstance(team, TeamInput):
                stored_team = await self._create_team(team)
                team_tree._graph.replace_with_stored(node_id, stored_team)

            elif isinstance(team, TeamStored):
                pass
            else:
                raise ValueError("Only TeamInput and TeamStored may be added to team tree")

        for node_id in team_tree._graph.removed_nodes:
            await self._delete_team(node_id)

        for node_id in team_tree._graph.changed_nodes:
            team = team_tree.get_team(node_id)
            if not isinstance(team, TeamStored):
                raise ValueError("Can only commit changes to stored teams")
            await self._set_team(team)

        await self._create_edges(team_tree._graph.added_edges)
        await self._delete_edges(team_tree._graph.removed_edges)

    async def _create_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['team_trees']['create_edges'], edges=list(edges))

    async def _delete_edges(self, edges: Set[tuple[int, int]]):
        if edges:
            await self.tx.run(queries['team_trees']['delete_edges'], edges=list(edges))

    @staticmethod
    def team_record_to_team(record) -> TeamStored:
        record.pop('name_lower')
        if 'includes' in record:
            raise ValueError("Ensure the edge data is removed before converting to a team")

        affiliations = Affiliations()
        for key, value in record['affiliations'].items():
            record['affiliations'][Access[key]] = {v['id']: Affiliation(authorisation = Authorisation(v['authorisation']), heritable = v['heritable']) for v in value}
        for access in record['affiliations'].keys():
            for user_id in record['affiliations'][access]:
                affiliations.set_by_access(Access(access), user_id, record['affiliations'][access][user_id])
        record['affiliations'] = affiliations
        return TeamStored(**record)

    async def split(self, team_id):
        team_tree = await self.get(team_id=team_id)
        # Split a team tree by removing an edge
        team = team_tree.get_team(team_id)
        # The current admins become the new root admins, i.e. all are given heritable admin access
        for user_id in team_tree.get_affiliates(team_id, access=Access.ADMIN):
            for access in (Access.ADMIN, Access.READ):  # admin access includes read access
                team.affiliations.set_by_access(
                    access,
                    user_id,
                    Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True)
                )
        # But this should break other inherited access
        parent_id = team_tree.get_parent_id(team_id)
        # finally break the graph.
        team_tree._graph.remove_edge(parent_id, team_id)
        # store the changes
        await self._update(team_tree)
        # and remove the cached team tree to force refetch
        self.seen.pop(team_tree)
