from dataclasses import dataclass
from enum import IntEnum
from collections import MutableSequence
from dbtools.custom_exceptions import ProtectedRelationshipError
from dbtools.domain.events import Event
from dbtools.custom_exceptions import NoResultFoundError, ExistingUniqueRelationship
from dbtools.adapters.repositories.trackable_wrappers import TrackableObject
from typing import List, Tuple, Union


class User:

	def __init__(
			self,
			username: str,
			fullname: str,
			email: str,
			password_hash: str,
			confirmed: bool = False,
			id_: int = None
	):
		self.username = username
		self.fullname = fullname
		self.email = email
		self.password_hash = password_hash
		self.confirmed = confirmed
		self.id_ = id_

	@property
	def username_lower(self):
		return self.username.casefold()

	def __eq__(self, other):
		if isinstance(other, User):
			return self.id_ == other.id_
		raise NotImplementedError

	def __hash__(self):
		return hash(self.id_)


@dataclass(frozen=True)
class Team:
	name: str
	fullname: str


class AffiliationLevel(IntEnum):
	UNCONFIRMED = 0
	USER = 1
	ADMIN = 2


class Affiliation:
	def __init__(
			self,
			team: Team,
			level: AffiliationLevel
	):
		self._team = team
		self.level = level

	@property
	def team(self):
		return self._team

	def __eq__(self, other):
		if isinstance(other, Affiliation):
			return self.team == other.team
		raise NotImplementedError

	def __hash__(self):
		return hash(self.team)


class Affiliations(MutableSequence):
	def __init__(self, sequence: Union[Affiliation, List[Affiliation], Tuple[Affiliation]]):
		if isinstance(sequence, list):
			self._list = sequence
		elif isinstance(sequence, tuple):
			self._list = list(sequence)
		else:
			self._list = [sequence]

	def __getitem__(self, i: Union[int, slice]) -> Union[Affiliation, List]:
		return self._list[i]

	def __setitem__(self, i: int, ta: TrackableObject) -> None:
		self._list[i] = ta

	def __delitem__(self, i: int) -> None:
		raise ProtectedRelationshipError(
			'Affiliations cannot be deleted'
		)

	def __len__(self) -> int:
		return len(self._list)

	def __iter__(self):
		return self._list.__iter__()

	def insert(self, index: int, a: Affiliation) -> None:
		raise ProtectedRelationshipError(
			'New affiliations can only be appended'
		)

	def append(self, a: Affiliation) -> None:
		# rather than implement an ordered set
		# simply check for presence before appending,
		# this works because the eq and hash of affiliation are based only on the _team attribute.
		if a in self._list:
			raise ExistingUniqueRelationship('An affiliation to this team already exists')
		self._list.append(a)

	@property
	def primary(self) -> Affiliation:
		return self._list[0]

	@property
	def unconfirmed_teams(self) -> List[Team]:
		return [a.team for a in self._list if a.level == 0]

	@property
	def read_access_teams(self) -> List[Team]:
		return [a.team for a in self._list if a.level > 0]

	@property
	def admin_teams(self) -> List[Team]:
		return [a.team for a in self._list if a.level == 2]

	def get_by_team_name(self, team_name):
		try:
			return next(a for a in self._list if a.team.name == team_name)
		except StopIteration as e:
			raise NoResultFoundError from e


class Account:
	def __init__(
			self,
			user: User,
			affiliations: Affiliations
	):
		self.user = user
		self.affiliations = affiliations
		self.events: List[Event] = []

	def is_admin(self):
		return bool(self.affiliations.admin_teams)

	def __eq__(self, other):
		if isinstance(other, Account):
			return self.user == other.user
		raise NotImplementedError

	def __hash__(self):
		return hash(self.user)
