from enum import IntEnum
from collections import defaultdict
from collections.abc import MutableMapping, MutableSequence
from abc import abstractmethod
from src.dbtools.domain.events.accounts import Event
from src.dbtools.custom_exceptions import ProtectedRelationshipError
from pydantic import BaseModel

from typing import TYPE_CHECKING, _T, overload, Iterable

if TYPE_CHECKING:
    from typing import Union, ValuesView


class NamedEntityBase(BaseModel):
    name: str

    @property
    def name_lower(self) -> str:
        return self.name.casefold()

    def __hash__(self) -> int:
        return hash(self.name_lower)

    @abstractmethod
    def __eq__(self, other) -> bool:
        raise NotImplementedError


class UserBase(NamedEntityBase):
    name: str
    fullname: str
    email: str

    def __eq__(self, other) -> bool:
        if isinstance(other, UserBase):
            return self.name_lower == other.name_lower
        elif isinstance(other, str):
            return self.name_lower == other
        raise NotImplementedError


class UserInput(UserBase):
    password_hash: str
    email_verified: bool = False
    global_admin: bool = False


class UserOutput(UserBase):
    id: int


class UserStored(UserBase):
    password_hash: str
    email_verified: bool = False
    global_admin: bool = False
    id: int
    allowed_emails: set[str] = set()

    def __eq__(self, other) -> bool:
        if isinstance(other, int):
            return self.id == int
        super().__eq__(other)


class TeamBase(NamedEntityBase):
    name: str
    fullname: str

    def __eq__(self, other) -> bool:
        if isinstance(other, TeamBase):
            return self.name_lower == other.name_lower
        raise NotImplementedError


class TeamInput(TeamBase):
    pass


class TeamOutput(TeamBase):
    pass


class TeamStored(TeamBase):
    id: int
    admins: set[UserOutput]

    def __eq__(self, other) -> bool:
        if isinstance(other, int):
            return self.id == int
        super().__eq__(other)


class AffiliationLevel(IntEnum):
    UNCONFIRMED = 0
    USER = 1
    ADMIN = 2


class Affiliation(BaseModel):
    team: TeamBase
    level: AffiliationLevel
    primary: bool = False
    confirmed: bool = False


class Affiliations(MutableMapping):
    def __init__(self, affiliations: "Union[Affiliation, list[Affiliation], set[Affiliation], tuple[Affiliation]]"):
        self._name_lower_to_team: dict[str, TeamBase] = dict()
        self._team_to_level: dict[TeamBase, AffiliationLevel] = dict()
        self._level_to_teams: dict[AffiliationLevel, set[TeamBase]] = defaultdict(set)
        self._primary_team = None
        self._confirmed: set[TeamBase] = set()
        if isinstance(affiliations, (set, list, tuple)):
            for affiliation in affiliations:
                self.add(affiliation)
        elif isinstance(affiliations, Affiliation):
            self.add(affiliations)
        else:
            raise NotImplementedError

    def add(self, affiliation: Affiliation):
        if affiliation.team in self._team_to_level:
            raise ProtectedRelationshipError("Affiliation is already defined")
        self.__setitem__(affiliation.team, affiliation.level)
        if affiliation.primary:
            if self._primary_team and self._primary_team != affiliation.team:
                raise ProtectedRelationshipError("Primary team is already defined")
            self._primary_team = affiliation.team
        if affiliation.confirmed:
            self._confirmed.add(affiliation.team)

    def __setitem__(self, key: TeamBase, value: AffiliationLevel):
        self._name_lower_to_team[key.name_lower] = key
        if key in self._team_to_level:
            # remove existing entry in level to teams
            existing_level = self._team_to_level[key]
            self._level_to_teams[existing_level].remove(key)
        self._team_to_level[key] = value
        self._level_to_teams[value].add(key)

    def __getitem__(
            self,
            key: "Union[TeamBase, AffiliationLevel]"
    ) -> "Union[AffiliationLevel, set[TeamBase]]":
        if isinstance(key, TeamBase):
            return self._team_to_level[key]
        if isinstance(key, AffiliationLevel):
            return self._level_to_teams[key]
        raise NotImplementedError

    def __delitem__(self, key: TeamBase):
        if self._primary_team == key:
            raise ProtectedRelationshipError("Primary affiliations can not be deleted")
        if key in self._confirmed:
            raise ProtectedRelationshipError("Confirmed affiliations can not be deleted")
        del self._name_lower_to_team[key.name]
        del self._team_to_level[key]
        self._level_to_teams[AffiliationLevel('UNCONFIRMED')].remove(key)

    def __iter__(self):
        return iter(self._team_to_level)

    def __len__(self):
        return len(self._team_to_level)
    @property
    def primary_team(self) -> TeamBase:
        return self._primary_team

    @property
    def unconfirmed_teams(self) -> "set[TeamBase]":
        return self._level_to_teams[AffiliationLevel['UNCONFIRMED']]

    @property
    def user_teams(self) -> "set[TeamBase]":
        return self._level_to_teams[AffiliationLevel['USER']]

    @property
    def admin_teams(self) -> "set[TeamBase]":
        return self._level_to_teams[AffiliationLevel['ADMIN']]

    @property
    def max_level(self) -> AffiliationLevel:
        return max(self._level_to_teams.keys())

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
        if isinstance(v, (list, set, tuple)):
            for i in v:
                is_affiliation(i)
        else:
            is_affiliation(v)
        return v


class AccountBase(BaseModel):
    user: UserBase
    affiliations: Affiliations

    def __eq__(self, other):
        if isinstance(other, AccountBase):
            return self.user == other.user
        raise NotImplementedError

    def __hash__(self):
        return hash(self.user)


class AccountInput(AccountBase):
    user: UserInput


class AccountOutput(AccountBase):
    user: UserOutput


class AccountStored(AccountBase):
    user: UserStored
    events: "list[Event]" = []
