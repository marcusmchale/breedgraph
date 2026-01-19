from contextlib import asynccontextmanager

from src.breedgraph.adapters.neo4j.views.datasets import Neo4jDatasetsView
from src.breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from src.breedgraph.service_layer.queries.views.views import AbstractViewsHolder, AbstractViewsFactory

from src.breedgraph.adapters.neo4j.views.regions import Neo4jRegionsView
from src.breedgraph.adapters.neo4j.views.accounts import Neo4jAccountsView

from src.breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver

from typing import AsyncGenerator

class Neo4jViewsHolder(AbstractViewsHolder):

    def __init__(
            self,
            accounts: Neo4jAccountsView,
            regions: Neo4jRegionsView,
            datasets: Neo4jDatasetsView
    ):
        self.accounts = accounts
        self.regions = regions
        self.datasets = datasets


class Neo4jViewsFactory(AbstractViewsFactory):
    def __init__(
            self,
            state_store: AbstractStateStore,
            driver: Neo4jAsyncDriver
    ):
        super().__init__(driver, state_store)
        self.driver = driver

    @asynccontextmanager
    async def _get_views(self, user_id: int = None) -> AsyncGenerator[Neo4jViewsHolder, None]:
        async with self.driver.session() as session:
            accounts_view = Neo4jAccountsView(session=session, user_id=user_id)
            read_teams = await accounts_view.get_read_teams()
            yield Neo4jViewsHolder(
                accounts_view,
                Neo4jRegionsView(state_store=self.state_store, read_teams=read_teams, session=session),
                Neo4jDatasetsView(read_teams=read_teams, session=session)
            )
