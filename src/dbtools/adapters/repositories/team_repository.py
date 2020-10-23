import abc
from typing import List
from neo4j import Transaction
from dbtools.adapters.cypher import queries
from dbtools.domain import model


class TeamRepository(abc.ABC):

	@abc.abstractmethod
	def get(self, name: str) -> model.Team:
		raise NotImplementedError

	@abc.abstractmethod
	def get_all(self) -> List[model.Team]:
		raise NotImplementedError


class Neo4jTeamRepository(TeamRepository):

	def __init__(self, tx: Transaction):
		super().__init__()
		self.tx = tx

	def get(self, name: str) -> model.Team:
		record = self.tx.run(queries['get_team'], name=name).single()
		return model.Team(record['team']['name'], record['team']['fullname']) if record else None

	def get_all(self) -> List[model.Team]:
		result = self.tx.run(queries['get_all_teams'])
		yield [model.Team(record['name'], record['fullname']) for record in result]
