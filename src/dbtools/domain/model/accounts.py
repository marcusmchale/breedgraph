from typing import Optional
from enum import IntEnum
from collections.abc import MutableMapping
from dbtools.domain.events.accounts import Event
from dbtools.custom_exceptions import ProtectedRelationshipError
from typing import List, Set, Tuple, Union

from pydantic import BaseModel


class UserBase(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    fullname: Optional[str] = None

    @property
    def username_lower(self):
        return self.username.casefold()


class UserRegistered(UserBase):
    id: int
    email: str
    username: str
    fullname: str
    password_hash: str
    email_confirmed: bool = False

    def __eq__(self, other):
        if isinstance(other, UserRegistered):
            return self.id == other.id
        raise NotImplementedError

    def __hash__(self):
        return hash(self.id)


class Team(BaseModel):
    name: str
    fullname: str
    id: Optional[int] = None


class AffiliationLevel(IntEnum):
    UNCONFIRMED = 0
    USER = 1
    ADMIN = 2
    GLOBAL_ADMIN = 3


class Affiliation(BaseModel):
    team: Team
    level: AffiliationLevel
    primary: bool

    def __eq__(self, other):
        if isinstance(other, Affiliation):
            return self.team == other.team
        raise NotImplementedError

    def __hash__(self):
        return hash(self.team)


class Affiliations(MutableMapping):

    def __init__(self, affiliations: Union[Affiliation, List[Affiliation], Set[Affiliation], Tuple[Affiliation]]):
        self._map = dict()
        self._primary = None
        if isinstance(affiliations, (set, list, tuple)):
            for affiliation in affiliations:
                self.add(affiliation)
        elif isinstance(affiliations, Affiliation):
            self.add(affiliations)

    def add(self, affiliation: Affiliation):
        self._map[affiliation.team] = affiliation.level
        if affiliation.primary:
            self._primary = affiliation.team

    def __setitem__(self, key: Team, value: AffiliationLevel):
        self._map[key] = value

    def __getitem__(self, key: [Team, str]) -> AffiliationLevel:
        if isinstance(key, Team):
            return self._map[key]

    def __delitem__(self, key: Team):
        raise ProtectedRelationshipError

    def __iter__(self):
        return iter(self._map)

    def __len__(self):
        return len(self._map)

    @property
    def primary(self) -> Team:
        return self._primary

    @property
    def all(self) -> List[Team]:
        return [key for key, value in self._map]

    @property
    def unconfirmed(self) -> List[Team]:
        return [key for key, value in self._map if value == AffiliationLevel.UNCONFIRMED]

    @property
    def user(self) -> List[Team]:
        return [key for key, value in self._map if value >= AffiliationLevel.USER]

    @property
    def admin(self) -> List[Team]:
        return [key for key, value in self._map if value >= AffiliationLevel.ADMIN]

    @property
    def max_level(self):
        return max(self._map.values())

    def get_by_team_name(self, team_name):
        for team, level in self._map:
            if team.name == team_name:
                return Affiliation(
                    team=team,
                    level=level,
                    primary=team == self.primary
                )

    # for pydantic validation
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):

        error_message = "Must be an Affiliation or list (or set or tuple) thereof"

        def is_affiliation(affiliation):
            if not isinstance(affiliation, Affiliation):
                raise ValueError(error_message)

        if not v:
            raise ValueError(error_message)

        if isinstance(v, (List, Set, Tuple)):
            for i in v:
                is_affiliation(i)
        else:
            is_affiliation(v)

        return v


class Account(BaseModel):
    user: UserRegistered
    affiliations: Affiliations
    events: List[Event] = []

    def __eq__(self, other):
        if isinstance(other, Account):
            return self.user == other.user
        raise NotImplementedError

    def __hash__(self):
        return hash(self.user)
