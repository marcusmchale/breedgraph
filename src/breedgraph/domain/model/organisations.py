import networkx as nx
import copy

from pydantic import BaseModel, computed_field
from enum import Enum

from src.breedgraph.domain.model.base import TreeAggregate, StoredModel, LabeledModel
from src.breedgraph.custom_exceptions import UnauthorisedOperationError, IllegalOperationError

from src.breedgraph.domain.events.accounts import AffiliationRequested, AffiliationApproved

from typing import List, ClassVar, Tuple

import logging


logger = logging.getLogger(__name__)

class Access(str, Enum):
    READ = 'READ'
    WRITE = 'WRITE'
    ADMIN = 'ADMIN'
    CURATE = 'CURATE'

class Authorisation(str, Enum):
    # authorisation may be removed by admin or user at any level
    REQUESTED = 'REQUESTED'  # admin may authorise
    AUTHORISED = 'AUTHORISED'  # admin may revoke
    # revoke is to allow an admin to disable access but re-authorise without a repeated request from the user.
    REVOKED = 'REVOKED'  # admin may authorise, user may request

class Affiliation(BaseModel):
    authorisation: Authorisation
    heritable: bool  # if heritable equivalent access is provided to all children, recursively

class TeamBase(LabeledModel):
    label: ClassVar[str] = 'Team'
    plural: ClassVar[str] = 'Teams'

    name: str
    fullname: str = None

class TeamInput(TeamBase):
    pass

class TeamStored(TeamBase, StoredModel):
    affiliations: dict[Access, dict[int, Affiliation]] = {a: dict() for a in Access}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def redacted(self):
        return self.model_copy(deep=True, update={'affiliations':dict()})

class TeamOutput(TeamStored):
    parent: int|None
    children: list[int]

class Organisation(TreeAggregate):

    def __init__(self, nodes: List[TeamStored|TeamInput] = None, edges: List[Tuple[int, int, dict]]|None = None):
        super().__init__(nodes=nodes, edges=edges)
        if nodes:
            for a in self.root.affiliations.get(Access.ADMIN, dict()).values():
                if a.heritable and a.authorisation is Authorisation.AUTHORISED:
                    break
            else:
                raise ValueError('Root must have a heritable authorisation affiliation')

    def get_team(self, team: int|str) -> TeamStored|TeamInput:
        if isinstance(team, int):
            return self.graph.nodes[team].get('model')
        elif isinstance(team, str):
            for t in self.teams.values():
                if t.name.casefold() == team.casefold():
                    return t

    def add_team(self, team: TeamInput, parent_id: int|None=None):
        if parent_id is not None and not parent_id in self.graph.nodes:
            raise ValueError("Parent not found")

        try:
            if parent_id is not None:
                for child_id, child_team in self.get_sinks(parent_id).items():

                    if child_team.name.lower() == team.name.lower():
                        raise ValueError('The parent team already has a child with this name')

        except TypeError:
            import pdb; pdb.set_trace()

        team_id = self._add_node(team)
        if parent_id is not None:
            self._add_edge(source_id=parent_id, sink_id=team_id)
        return team_id

    def remove_team(self, team_id: int):
        if self.get_sinks(team_id):
            raise IllegalOperationError("Cannot remove a team with children")

        self.graph.remove_node(team_id)

    @computed_field
    def teams(self) -> List[TeamStored|TeamInput]:
        return nx.get_node_attributes(self.graph, 'model')

    @staticmethod
    def get_access_levels(access: Access|List[Access] = None):
        if access is None:
            return [a for a in Access]
        elif isinstance(access, Access):
            return [access]
        elif isinstance(access, list):
            return access

    @staticmethod
    def get_auth_levels(authorisation: Authorisation|List[Authorisation] = None):
        if authorisation is None:
            return [a for a in Authorisation]
        elif isinstance(authorisation, Authorisation):
            return [authorisation]
        elif isinstance(authorisation, list):
            return authorisation

    def get_affiliates(
            self,
            team_id: int,
            access: Access|List[Access]|None = None,
            authorisation: Authorisation|List[Authorisation]|None = Authorisation.AUTHORISED,
            inheritance: bool = True
    ) -> set[int]:
        """
        :param team_id: A team ID to look up
        :param access: Optional access level or list of access levels, if None then all levels, default is none (i.e all)
        :param authorisation: Optional authorisation level or list of authorisation levels, if None then all levels, default is Authorised
        :param inheritance: boolean, whether to consider inheritance or just look at the given team, default is True
        :return: Returns a set of affiliates (user id)
        """
        team = self.get_team(team_id)
        affiliates = set()
        authorisation_levels = self.get_auth_levels(authorisation)
        for access_level in self.get_access_levels(access):
            affiliates = affiliates.union(set([u for u,a in team.affiliations.get(Access[access_level], {}).items() if a.authorisation in authorisation_levels]))
            # collect heritable affiliations from predecessors
            if inheritance:
                for p in self.graph.predecessors(team_id):
                    predecessor = self.get_team(p)
                    affiliates = affiliates.union(set([u for u,a in predecessor.affiliations.get(Access[access_level], {}).items() if a.authorisation in authorisation_levels and a.heritable]))
        return affiliates

    def request_affiliation(self, agent_id: int, team_id:int, access: Access, user_id: int, heritable: bool = True) -> None:
        if not agent_id == user_id:
            raise IllegalOperationError("Requests may only be made by the given user")

        team = self.get_team(team_id)
        affiliation = team.affiliations.get(access,{}).get(user_id, None)

        # to handle repeated requests or requests that are unintended
        if affiliation is not None and affiliation.authorisation is Authorisation.REQUESTED:
            logger.debug(f"Affiliation request already exists, doing nothing")
            return
        elif affiliation is not None and affiliation.authorisation is Authorisation.AUTHORISED:
            logger.debug(f"Affiliation already authorised, doing nothing")
            return

        if not access in team.affiliations:
            team.affiliations[access] = dict()

        team.affiliations[access][user_id] = Affiliation(authorisation=Authorisation.REQUESTED, heritable=heritable)

        self.events.append(AffiliationRequested(user=user_id, team=team_id, access=access))

    def remove_affiliation(self, agent_id: int, team_id: int, access: Access, user_id: int):
        if not any([
            agent_id == user_id,
            agent_id in self.get_affiliates(team_id, access=Access.ADMIN)
        ]):
            raise UnauthorisedOperationError("Only the given user or admins for the given team may remove affiliations")

        team = self.get_team(team_id)
        del team.affiliations[access][user_id]

    def authorise_affiliation(
            self,
            agent_id: int,
            team_id: int,
            access: Access,
            user_id: int,
            heritable: bool = False
    ) -> None:
        """
        If a direct or inherited affiliation to this team is found then authorise the provided affiliation.
        May only be performed by an agent that is admin for the given team

        :param agent_id:
        :param team_id:
        :param access:
        :param user_id:
        :param heritable:
        :return: None
        """
        if not agent_id in self.get_affiliates(team_id, Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team may authorise affiliations")

        affiliates = self.get_affiliates(team_id, authorisation=None)
        if not user_id in affiliates:
            raise IllegalOperationError(f"No affiliation found to team: {team_id} for user: {user_id}")

        team = self.get_team(team_id)
        team.affiliations[access][user_id] = Affiliation(
            authorisation=Authorisation.AUTHORISED,
            heritable=heritable
        )
        self.events.append(AffiliationApproved(user=user_id, team=team_id, access=access))

    def revoke_affiliation(self, agent_id: int, team_id: int, access: Access, user_id: int) -> None:
        if not agent_id in self.get_affiliates(team_id, Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team may revoke affiliations")

        team = self.get_team(team_id)
        affiliation = team.affiliations[access][user_id]
        affiliation.authorisation = Authorisation.REVOKED

    def redacted(self, user_id: int = None) -> 'Organisation':
        g = copy.deepcopy(self.graph)
        root_id = self.get_root_id()
        for node_id in list(g.nodes):
            entry: TeamStored = g.nodes[node_id]['model']
            readers = self.get_affiliates(node_id, access=Access.READ)
            writers = self.get_affiliates(node_id, access=Access.WRITE)
            admins =  self.get_affiliates(node_id, access=Access.ADMIN)
            curators = self.get_affiliates(node_id, access=Access.CURATE)

            if not user_id in admins:
                g.nodes[node_id]['model'] = entry.redacted()

            if not user_id in readers | admins | writers | curators:
                if node_id == root_id:
                    pass
                else:
                    self.remove_node_and_reconnect(g, node_id, label=self.default_edge_label)

        aggregate = self.__class__()
        aggregate.graph = g
        return aggregate

    def to_output_map(self) -> dict[int, TeamOutput]:
        # this creates a dictionary where each node maps to list of neighbours
        return {node: TeamOutput(
            **self.get_team(node).model_dump(),
            parent=self.get_parent_id(node),
            children=self.get_children_ids(node)
        ) for node in self.graph}