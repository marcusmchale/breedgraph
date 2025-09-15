from abc import ABC
from dataclasses import dataclass, field, replace
from copy import deepcopy
from enum import Enum
import networkx as nx

from src.breedgraph.domain.model.base import StoredModel, LabeledModel
from src.breedgraph.domain.model.graph import TreeAggregate
from src.breedgraph.custom_exceptions import UnauthorisedOperationError, IllegalOperationError
from src.breedgraph.domain.events.accounts import AffiliationRequested, AffiliationApproved

from typing import List, ClassVar, Tuple, Dict, Any, Self

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

@dataclass
class Affiliation:
    authorisation: Authorisation
    heritable: bool  # if heritable equivalent access is provided to all children, recursively

@dataclass
class Affiliations:
    """
    A Pydantic model to represent team affiliations organized by access level.
    Each dict is keyed by user ID and contains an Affiliation object.
    """
    read: dict[int, Affiliation] = field(default_factory = dict)
    write: dict[int, Affiliation] = field(default_factory = dict)
    admin: dict[int, Affiliation] = field(default_factory = dict)
    curate: dict[int, Affiliation] = field(default_factory = dict)

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

@dataclass
class TeamBase(ABC):
    label: ClassVar[str] = 'Team'
    plural: ClassVar[str] = 'Teams'

    name: str = ''
    fullname: str = None

@dataclass
class TeamInput(TeamBase, LabeledModel):
    pass

@dataclass
class TeamStored(TeamBase, StoredModel):
    """
    Affiliations is a representation of team affiliations organized by access level.
    Each access level contains a mapping of user IDs to their affiliation details.
    """
    affiliations: Affiliations = field(default_factory = Affiliations)

    def redacted(self, user_id: int = None) -> 'TeamStored':
        return replace(self, affiliations=self.affiliations.get_redacted_copy(user_id))

@dataclass
class TeamOutput(TeamBase, StoredModel):
    parent: int|None = None
    children: list[int] = field(default_factory=list)

    direct_affiliations: Affiliations = field(default_factory=Affiliations)
    inherited_affiliations: Affiliations = field(default_factory=Affiliations)

    @property
    def affiliations(self) -> Affiliations:
        """
        Merge direct and inherited affiliations into a single Affiliations object.
        Since inherited affiliations exclude users with direct affiliations,
        we can simply combine both without conflicts.
        """
        merged_affiliations = Affiliations()

        # Add both direct and inherited affiliations for each access level
        for access in Access:
            # Add direct affiliations
            direct_for_access = self.direct_affiliations.get_by_access(access)
            for user_id, affiliation in direct_for_access.items():
                merged_affiliations.set_by_access(access, user_id, affiliation)

            # Add inherited affiliations (no conflicts since they exclude direct users)
            inherited_for_access = self.inherited_affiliations.get_by_access(access)
            for user_id, affiliation in inherited_for_access.items():
                merged_affiliations.set_by_access(access, user_id, affiliation)

        return merged_affiliations

    @classmethod
    def from_stored(
            cls,
            stored: TeamStored,
            parent: int|None = None,
            children: List[int] = None,
            inherited_affiliations: Affiliations = None
    ) -> Self:
        return cls(
            id=stored.id,
            name=stored.name,
            fullname=stored.fullname,
            direct_affiliations=stored.affiliations,
            parent=parent,
            children=children or [],
            inherited_affiliations=inherited_affiliations or Affiliations()
        )

TInput = TeamInput
TOutput = TeamOutput
TStored = TeamStored

class Organisation(TreeAggregate):
    default_edge_label: ClassVar['str'] = "INCLUDES_TEAM"

    def __init__(self, nodes: List[TeamStored|TeamInput] = None, edges: List[Tuple[int, int, dict]]|None = None):
        self.redaction_mapping = None
        super().__init__(nodes=nodes, edges=edges)
        if nodes:
            for a in self.root.affiliations.get_by_access(Access.ADMIN).values():
                if a.heritable and a.authorisation is Authorisation.AUTHORISED:
                    break
            else:
                raise ValueError('Root must have at least one heritable authorised Admin affiliation')

    def get_team(self, team: int|str) -> TeamStored|TeamInput|None:
        if isinstance(team, int):
            return self._graph.nodes[team].get('model')
        elif isinstance(team, str):
            for t in self.teams:
                if t.name.casefold() == team.casefold():
                    return t
        return None

    def get_children(self, team_id: int) -> List[int]:
        return list(self._graph.successors(team_id))

    def get_parent_id(self, team_id: int) -> int|None:
        return next(self._graph.predecessors(team_id), None)

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

    @property
    def teams(self) -> List[TeamStored|TeamInput]:
        return list(self.entries.values())

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
            # Get direct affiliations from the team
            direct_affiliations = team.affiliations.get_by_access(access_level)
            affiliates.update(
                user_id for user_id, affiliation in direct_affiliations.items()
                if affiliation.authorisation in authorisation_levels
            )

            # Get inherited affiliations if requested
            if inheritance:
                inherited_affiliations = self.get_inherited_affiliations(team_id)
                inherited_for_access = inherited_affiliations.get_by_access(access_level)
                affiliates.update(
                    user_id for user_id, affiliation in inherited_for_access.items()
                    if affiliation.authorisation in authorisation_levels
                )

        return affiliates

    def get_inherited_affiliations(
            self,
            team_id: int
    ) -> Affiliations:
        """
        Returns inherited affiliations for a given team, excluding any access levels
        where the user has direct affiliations (closest wins principle).

        :param team_id:
        :return Affiliations: An Affiliations object with only truly inherited affiliations.
        """
        team = self.get_team(team_id)
        affiliations = Affiliations()

        # Process ancestors from closest to furthest
        for ancestor_id in self.get_ancestors(team_id):
            ancestor = self.get_team(ancestor_id)
            heritable_affiliations = ancestor.affiliations.get_heritable_copy()

            for access in Access:
                for user_id in heritable_affiliations.get_by_access(access):
                    # Skip if user has direct affiliation for this access level (closest wins)
                    if user_id in team.affiliations.get_by_access(access):
                        continue

                    # Skip if we've already set an inherited affiliation for this user/access
                    if user_id in affiliations.get_by_access(access):
                        continue

                    incoming_affiliation = heritable_affiliations.get_by_access(access)[user_id]
                    affiliations.set_by_access(access, user_id, incoming_affiliation)

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
        g = deepcopy(self._graph)
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
        team_map = {
            team.id: TeamOutput.from_stored(
                team,
                parent=self.get_parent_id(team.id),
                children=self.get_children_ids(team.id),
                inherited_affiliations=self.get_inherited_affiliations(team.id)
            ) for team in self.teams
        }
        if self.redaction_mapping is not None:
            # we map from removed teams to the visible source node in the redacted map
            # this way a user only sees the most relevant controlling team information that they have access to.
            for key, value in self.redaction_mapping.items():
                team_map[key] = team_map[value]
        return team_map