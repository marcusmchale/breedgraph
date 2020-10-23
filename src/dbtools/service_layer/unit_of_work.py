import abc
import logging
from neo4j import GraphDatabase, Transaction
from dbtools.adapters.repositories import team_repository, allowed_email_repository, account_repository
from dbtools.config import get_bolt_uri, get_graphdb_auth, NEO4J_DRIVER_LOG


class AbstractUnitOfWork(abc.ABC):
	emails: allowed_email_repository.AllowedEmailRepository
	teams: team_repository.TeamRepository
	accounts: account_repository.AccountRepository

	def __enter__(self) -> 'AbstractUnitOfWork':
		return self

	def __exit__(self, *args):
		self.close()

	@abc.abstractmethod
	def commit(self):
		raise NotImplementedError

	@abc.abstractmethod
	def rollback(self):
		raise NotImplementedError

	@abc.abstractmethod
	def close(self):
		raise NotImplementedError

	def collect_new_events(self):
		for account in self.accounts.seen:
			while account.events:
				yield account.events.pop(0)


class Neo4jUnitOfWork(AbstractUnitOfWork):

	def __init__(self):
		self.driver = GraphDatabase.driver(
			get_bolt_uri(),
			auth=get_graphdb_auth(),
			connection_timeout=5,
			connection_acquisition_timeout=5,
			max_transaction_retry_time=5
		)

	def __enter__(self):
		self.session = self.driver.session()
		self.tx: Transaction = self.session.begin_transaction()
		self.emails = allowed_email_repository.Neo4jAllowedEmailRepository(self.tx)
		self.teams = team_repository.Neo4jTeamRepository(self.tx)
		self.accounts = account_repository.Neo4jAccountRepository(self.tx)
		return super().__enter__()

	def commit(self):
		self.accounts.update_all()
		self.tx.commit()

	def rollback(self):
		self.tx.rollback()

	def close(self):
		self.tx.close()  # rolls back any outstanding transactions
