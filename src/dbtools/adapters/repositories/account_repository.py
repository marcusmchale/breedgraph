from abc import ABC, abstractmethod
from typing import Set
from neo4j import Transaction, Record
from dbtools.adapters.cypher import queries
from dbtools.domain.model import User, Team, Affiliation, AffiliationLevel, Affiliations, Account
from dbtools.adapters.repositories.trackable_wrappers import TrackableObject, TrackableSequence
from dbtools.custom_exceptions import ProtectedNodeError


class AccountRepository(ABC):
	# todo will need to consider a "reset_tracking" function
	#  where changes must be committed over multiple transactions
	#  e.g. batching of submissions when a single transaction is too big to be kep in memory
	#  not likely with accounts but very much so when tackling records

	def __init__(self):
		self.seen: Set[Account] = set()

	def _track(self, account: Account):
		account.user = TrackableObject(account.user)
		account.affiliations = TrackableSequence([TrackableObject(a) for a in account.affiliations])
		self.seen.add(account)

	def add(self, account: Account):
		self._add(account)
		self._track(account)

	@abstractmethod
	def _add(self, account: Account):
		raise NotImplementedError

	def get(self, username: str) -> Account:
		account = self._get(username.casefold())
		if account:
			self._track(account)
		return account

	@abstractmethod
	def _get(self, username_lower: str) -> Account:
		raise NotImplementedError

	def get_by_email(self, email: str) -> Account:
		account = self._get_by_email(email)
		if account:
			self._track(account)
		return account

	@abstractmethod
	def _get_by_email(self, email: str) -> Account:
		raise NotImplementedError

	def remove(self, account: Account):
		if account.user.confirmed:
			raise ProtectedNodeError
		self._remove(account)

	@abstractmethod
	def _remove(self, account: Account):
		raise NotImplementedError

	def update_all(self):
		for account in self.seen:
			self.update(account)

	def update(self, account: Account):
		# note that some of the automated type checking for this function fails due to issues with the proxy classes
		# for example the dirty and source len flags aren't on the source models
		# as the "account" is modified by replacing many of its attributes with proxies
		# (recursively in the case of affiliations)
		#
		# if the user details have changed (dirty is a flag added to the tracking wrapper)
		if account.user.dirty:
			self._update_user(account.user)
		# the tracking wrapper on affiliations stores the original length
		# as the affiliations object only allows append
		# we can afford to only update the original items (i.e. set the level) ...
		source_len = account.affiliations.source_len
		for affiliation in account.affiliations[:source_len]:
			if affiliation.dirty:
				self._update_affiliation(account.user, affiliation)
		# ... and then add any new affiliations and wrap them to track future changes
		for i, affiliation in enumerate(account.affiliations[source_len:]):
			self._add_affiliation(account.user, affiliation)
			index_position = source_len + i
			account.affiliations[index_position] = TrackableObject(affiliation)

	@abstractmethod
	def _update_user(self, user: User):
		raise NotImplementedError

	@abstractmethod
	def _add_affiliation(self, user: User, affiliation: Affiliation):
		raise NotImplementedError

	@abstractmethod
	def _update_affiliation(self, user:User, affiliation: Affiliation):
		raise NotImplementedError


class Neo4jAccountRepository(AccountRepository):

	def __init__(self, tx: Transaction):
		super().__init__()
		self.tx = tx

	def _add(self, account: Account):
		record = self.tx.run(
			queries['add_account'],
			username=account.user.username,
			username_lower=account.user.username_lower,
			fullname=account.user.fullname,
			password_hash=account.user.password_hash,
			email=account.user.email,
			team_name=account.affiliations.primary.team.name
		).single()
		account.id = record[0]

	def _get(self, username_lower: str) -> Account:
		record: Record = self.tx.run(queries['get_account'], username_lower=username_lower).single()
		return self.record_to_account(record) if record else None

	def _get_by_email(self, email: str) -> Account:
		record: Record = self.tx.run(queries['get_account_by_email'], email=email).single()
		return self.record_to_account(record) if record else None

	def _remove(self, account: Account):
		self.tx.run(queries['delete_unconfirmed_account'], email=account.user.email)

	def _update_user(self, user: User):
		self.tx.run(
			queries('update_user'),
			id=user.id_,
			username=user.username,
			username_lower=user.username_lower,
			fullname=user.fullname,
			password_hash=user.password_hash,
			email=user.email
		)

	def _update_affiliation(self, user: User, affiliation: Affiliation):
		self.tx.run(
			queries('update_affiliation'),
			username_lower=user.username_lower,
			team_name=affiliation.team.name,
			level=affiliation.level.value
		)

	def _add_affiliation(self, user: User, affiliation: Affiliation):
		self.tx.run(
			queries('add_affiliation'),
			username_lower=user.username_lower,
			team_name=affiliation.team.name
		)

	@staticmethod
	def record_to_account(record: Record) -> Account:
		user = User(
			username=record['user']['username'],
			fullname=record['user']['fullname'],
			email=record['user']['email'],
			password_hash=record['user']['password_hash'],
			confirmed=record['user']['confirmed'],
			id_=record['user']['id']
		)
		affiliations = Affiliations([
			Affiliation(
				Team(team_name, team_fullname),
				AffiliationLevel(affiliation_level)
			) for team_name, team_fullname, affiliation_level in record['affiliations']
		])
		return Account(
			user=user,
			affiliations=affiliations
		)


class FakeAccountRepository(AccountRepository):

	def __init__(self):
		super().__init__()
		self._accounts = set()

	def _add(self, account: Account):
		self._accounts.add(account)

	def _get(self, username_lower: str) -> Account:
		return next(a for a in self._accounts if a.user.username_lower == username_lower)

	def _get_by_email(self, email: str) -> Account:
		return next(a for a in self._accounts if a.user.email == email)

	def _remove(self, account: Account):
		self._accounts.remove(account)

	def _update_user(self, user: User):
		pass

	def _add_affiliation(self, user: User, affiliation: Affiliation):
		pass

	def _update_affiliation(self, user: User, affiliation: Affiliation):
		pass
