from neo4j import AsyncTransaction, AsyncResult
from typing import AsyncGenerator

from src.breedgraph.adapters.neo4j.views.regions import Neo4jRegionsViews
from src.breedgraph.adapters.neo4j.views.accounts import Neo4jAccountsViews
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService
from src.breedgraph.domain.model.regions import LocationOutput, LocationStored
from src.breedgraph.service_layer.queries.views import AbstractViewsHolder

from src.breedgraph.adapters.neo4j.cypher import queries

from src.breedgraph.domain.model.accounts import UserOutput
from src.breedgraph.domain.model.controls import Access

from typing import Dict, Set

class Neo4jViewsHolder(AbstractViewsHolder):
    def __init__(
            self, tx: AsyncTransaction,
            access_control: AbstractAccessControlService,
            user_id: int = None,
            access_teams: Dict[Access, Set[int]] = None
    ):
        self.tx = tx
        self.access_control = access_control
        self.user_id = user_id
        self.access_teams = access_teams

        self.regions = Neo4jRegionsViews(tx, access_control)
        self.accounts = Neo4jAccountsViews(tx)