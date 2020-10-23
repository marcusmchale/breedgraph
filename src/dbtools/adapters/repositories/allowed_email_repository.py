from abc import ABC, abstractmethod
from neo4j import Transaction
from dbtools.adapters.cypher import queries
from dbtools.domain import model


class AllowedEmailRepository(ABC):

	@abstractmethod
	def add(self, admin: model.User, email: str):
		raise NotImplementedError

	@abstractmethod
	def get(self, email: str) -> str:
		raise NotImplementedError

	@abstractmethod
	def exists(self, email:str) -> bool:
		raise NotImplementedError

	@abstractmethod
	def remove(self, admin: model.User, email: str):
		raise NotImplementedError


class Neo4jAllowedEmailRepository(AllowedEmailRepository):

	def __init__(self, tx: Transaction):
		super().__init__()
		self.tx = tx

	def add(self, admin: model.User, email: str):
		self.tx.run(queries['add_email'], admin_name_lower=admin.username_lower, email=email)

	def get(self, email: str) -> str:
		record = self.tx.run(queries['get_email'], email=email).single()
		return record[0] if record else None

	def exists(self, email: str) -> bool:
		record = self.tx.run(queries['get_email'], email=email).single()
		return True if record else False

	def remove(self, admin: model.User, email: str):
		self.tx.run(queries['remove_email'], admin_name_lower=admin.username_lower, email=email)
