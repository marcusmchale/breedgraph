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

class Affiliations(BaseModel):
    """
    A Pydantic model to represent team affiliations organized by access level.
    Each dict is keyed by user ID and contains an Affiliation object.
    """
    read: dict[int, Affiliation] = {}
    write: dict[int, Affiliation] = {}
    admin: dict[int, Affiliation] = {}
    curate: dict[int, Affiliation] = {}

    def get_by_access(self, access: Access) -> dict[int, Affiliation]:
        """Get affiliations for a specific access level."""
        return getattr(self, access.value.lower())

    def set_by_access(self, access: Access, user_id: int, affiliation: Affiliation):
        """Set an affiliation for a specific access level and user."""
        affiliations_dict = self.get_by_access(access)
        affiliations_dict[user_id] = affiliation

    def remove_by_access(self, access: Access, user_id: int):
        """Remove an affiliation for a specific access level and user."""
        affiliations_dict = self.get_by_access(access)
        if user_id in affiliations_dict:
            del affiliations_dict[user_id]

    def get_heritable_copy(self) -> 'Affiliations':
        """Return a copy of TeamAffiliations containing only heritable affiliations."""
        heritable_affiliations = Affiliations()

        # Iterate through all access levels
        for access in Access:
            affiliations_dict = self.get_by_access(access)
            heritable_dict = heritable_affiliations.get_by_access(access)

            # Copy only heritable affiliations
            for user_id, affiliation in affiliations_dict.items():
                if affiliation.heritable:
                    heritable_dict[user_id] = affiliation

        return heritable_affiliations

    def get_redacted_copy(self, user_id: int = None) -> 'Affiliations':
        """Return a copy of TeamAffiliations with all affiliations other than the supplied user redacted."""
        affiliations = Affiliations()
        for access in Access:
            access_affiliations = self.get_by_access(access)
            if user_id in access_affiliations:
                affiliations.set_by_access(access, user_id, access_affiliations[user_id])
        return affiliations

class TeamBase(LabeledModel):
    label: ClassVar[str] = 'Team'
    plural: ClassVar[str] = 'Teams'

    name: str
    fullname: str = None

class TeamInput(TeamBase):
    pass

class TeamStored(TeamBase, StoredModel):
    """
    Affiliations is a representation of team affiliations organized by access level.
    Each access level contains a mapping of user IDs to their affiliation details.
    """
    affiliations: Affiliations = Affiliations()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def redacted(self, user_id: int = None) -> 'TeamStored':
        model_copy = self.model_copy(deep=True)
        model_copy.affiliations = model_copy.affiliations.get_redacted_copy(user_id = user_id)
        return model_copy

class TeamOutput(TeamStored):
    parent: int|None
    children: list[int]

class Organisation(TreeAggregate):
    redaction_mapping: dict = None

    def __init__(self, nodes: List[TeamStored|TeamInput] = None, edges: List[Tuple[int, int, dict]]|None = None):

        super().__init__(nodes=nodes, edges=edges)
        if nodes:
            for a in self.root.affiliations.get_by_access(Access.ADMIN).values():
                if a.heritable and a.authorisation is Authorisation.AUTHORISED:
                    break
            else:
                raise ValueError('Root must have at least one heritable authorised Admin affiliation')

    def get_team(self, team: int|str) -> TeamStored|TeamInput:
        if isinstance(team, int):
            return self._graph.nodes[team].get('model')
        elif isinstance(team, str):
            for t in self.teams.values():
                if t.name.casefold() == team.casefold():
                    return t

    def add_team(self, team: TeamInput, parent_id: int|None=None):
        if parent_id is not None and not parent_id in self._graph.nodes:
            raise ValueError("Parent not found")

        if parent_id is not None:
            for child_id, child_team in self.get_sinks(parent_id).items():
                if child_team.name.lower() == team.name.lower():
                    raise ValueError('The parent team already has a child with this name')

        team_id = self._add_node(team)
        if parent_id is not None:
            self._add_edge(source_id=parent_id, sink_id=team_id)
        return team_id

    def remove_team(self, team_id: int):
        if self.get_sinks(team_id):
            raise IllegalOperationError("Cannot remove a team with children")
        self._graph.remove_node(team_id)

    def split(self, team_id):
        # Split an organisation by removing an edge
        team = self.get_team(team_id)
        # The current admins become the new root admins, i.e. all are given heritable admin access
        for user_id in self.get_affiliates(team_id, access=Access.ADMIN):
            team.affiliations.set_by_access(
                Access.ADMIN,
                user_id,
                Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True)
            )
        # But this should break other inherited access
        parent_id = self.get_parent_id(team_id)
        # finally break the graph.
        self._graph.remove_edge(parent_id, team_id)

    @computed_field
    def teams(self) -> List[TeamStored|TeamInput]:
        return nx.get_node_attributes(self._graph, 'model')

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
            affiliates = affiliates.union(set([u for u,a in team.affiliations.get_by_access(access_level).items() if a.authorisation in authorisation_levels]))
            # collect heritable affiliations from ancestors
            if inheritance:
                for p in nx.ancestors(self._graph, team_id):
                    ancestor = self.get_team(p)
                    affiliates = affiliates.union(set([u for u,a in ancestor.affiliations.get_by_access(access_level).items() if a.authorisation in authorisation_levels and a.heritable]))
        return affiliates

    def get_inherited_affiliations(
            self,
            team_id: int
    ) -> Affiliations:
        """
        Returns affiliations for a given team including inherited affiliations.

        :param team_id:
        :return Affiliations: An Affiliations object detailing inherited affiliations.
        """
        affiliations = Affiliations()
        for p in nx.ancestors(self._graph, team_id):
            ancestor = self.get_team(p)
            heritable_affiliations = ancestor.affiliations.get_heritable_copy()
            for access in Access:
                for user_id in heritable_affiliations.get_by_access(access):
                    incoming_affiliation = heritable_affiliations.get_by_access(access)[user_id]
                    if user_id not in affiliations.get_by_access(access):
                        affiliations.set_by_access(access, user_id, incoming_affiliation)
                    else:
                        stored_affiliation = affiliations.get_by_access(access)[user_id]
                        if stored_affiliation.authorisation is Authorisation.REVOKED:
                            affiliations.set_by_access(access, user_id, incoming_affiliation)
                        elif stored_affiliation.authorisation is Authorisation.REQUESTED and not incoming_affiliation.authorisation is Authorisation.REVOKED:
                            affiliations.set_by_access(access, user_id, incoming_affiliation)
                        else:
                            # stored_affiliation.authorisation must be approved, so don't replace it
                            continue
        return affiliations

    def request_affiliation(self, agent_id: int, team_id:int, access: Access, user_id: int, heritable: bool = True) -> None:
        if not agent_id == user_id:
            raise IllegalOperationError("Requests may only be made by the given user")

        team = self.get_team(team_id)
        affiliation = team.affiliations.get_by_access(access).get(user_id, None)

        # to handle repeated requests or requests that are unintended
        if affiliation is not None and affiliation.authorisation is Authorisation.REQUESTED:
            logger.debug(f"Affiliation request already exists, doing nothing")
            return
        elif affiliation is not None and affiliation.authorisation is Authorisation.AUTHORISED:
            logger.debug(f"Affiliation already authorised, doing nothing")
            return

        team.affiliations.set_by_access(access, user_id, Affiliation(authorisation=Authorisation.REQUESTED, heritable=heritable))

        self.events.append(AffiliationRequested(user=user_id, team=team_id, access=access))

    def remove_affiliation(self, agent_id: int, team_id: int, access: Access, user_id: int):
        if not any([
            agent_id == user_id,
            agent_id in self.get_affiliates(team_id, access=Access.ADMIN)
        ]):
            raise UnauthorisedOperationError("Only the given user or admins for the given team may remove affiliations")

        team = self.get_team(team_id)

        # we must ensure that removing this affiliation will not leave the team without an admin
        if access == Access.ADMIN:
            # Count remaining authorized admins (excluding the one being removed)
            remaining_authorized_admins = [
                (uid, aff) for uid, aff in team.affiliations.get_by_access(access).items()
                if uid != user_id and aff.authorisation == Authorisation.AUTHORISED
            ]

            if not remaining_authorized_admins:
                raise IllegalOperationError(
                    "Removing this admin affiliation would leave the team without any authorised admin")

            if team.id == self.root.id:
                has_heritable_admin = any(aff.heritable for uid, aff in remaining_authorized_admins)
                if not has_heritable_admin:
                    raise IllegalOperationError(
                        "Removing this admin affiliation would leave the root team without a heritable admin")

        team.affiliations.remove_by_access(access, user_id)

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

        affiliates = self.get_affiliates(team_id, authorisation=None, inheritance=True)

        if not user_id in affiliates:
            raise IllegalOperationError(f"No affiliation found to team: {team_id} for user: {user_id}")

        team = self.get_team(team_id)
        team.affiliations.set_by_access(
            access,
            user_id,
            Affiliation(authorisation=Authorisation.AUTHORISED, heritable=heritable)
        )
        self.events.append(AffiliationApproved(user=user_id, team=team_id, access=access))

    def revoke_affiliation(self, agent_id: int, team_id: int, access: Access, user_id: int) -> None:
        if not agent_id in self.get_affiliates(team_id, Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team may revoke affiliations")

        team = self.get_team(team_id)
        affiliation = team.affiliations.get_by_access(access)[user_id]
        affiliation.authorisation = Authorisation.REVOKED

    def redacted(self, user_id: int = None) -> 'Organisation':
        g = copy.deepcopy(self._graph)
        root_id = self.get_root_id()

        redaction_mapping = dict()

        for node_id in list(g.nodes):
            entry: TeamStored = g.nodes[node_id]['model']
            readers = self.get_affiliates(node_id, access=Access.READ)
            writers = self.get_affiliates(node_id, access=Access.WRITE)
            admins =  self.get_affiliates(node_id, access=Access.ADMIN)
            curators = self.get_affiliates(node_id, access=Access.CURATE)
            if not user_id in admins:
                g.nodes[node_id]['model'] = entry.redacted(user_id=user_id)

            if not user_id in readers | admins | writers | curators:
                if node_id == root_id:
                    pass
                else:
                    parent_id = self.get_parent_id(node_id)
                    redaction_mapping[node_id] = parent_id
                    self.remove_node_and_reconnect(g, node_id, label=self.default_edge_label)

        org = self.__class__()
        org._graph = g
        org.redaction_mapping = redaction_mapping
        return org

    def to_output_map(self) -> dict[int, TeamOutput]:
        # this creates a dictionary where each node maps to list of neighbours
        node_map = {node: TeamOutput(
            **self.get_team(node).model_dump(),
            parent=self.get_parent_id(node),
            children=self.get_children_ids(node)
        ) for node in self._graph }
        if self.redaction_mapping is not None:
            # we map from removed teams to the visible source node in the redacted map
            # this way a user can always see the most relevant controlling team information that they have access to.
            for key, value in self.redaction_mapping.items():
                node_map[key] = node_map[value]
        return node_map