from contextlib import asynccontextmanager

from breedgraph.adapters.neo4j.views.datasets import Neo4jDatasetsView
from breedgraph.adapters.neo4j.views.germplasm import Neo4jGermplasmView
from breedgraph.adapters.neo4j.views.ontology import Neo4jOntologyView
from breedgraph.adapters.neo4j.views.units import Neo4jUnitsView
from breedgraph.adapters.neo4j.views.programs import Neo4jProgramsView
from breedgraph.adapters.neo4j.views.layout_trees import Neo4jLayoutTreesView
from breedgraph.adapters.neo4j.views.references import Neo4jReferencesView
from breedgraph.adapters.neo4j.views.people import Neo4jPeopleView
from breedgraph.adapters.neo4j.views.controls import Neo4jControlsView
from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from breedgraph.service_layer.queries.views.views import AbstractViewsHolder, AbstractViewsFactory

from breedgraph.adapters.neo4j.views.location_trees import Neo4jLocationTreesView
from breedgraph.adapters.neo4j.views.accounts import Neo4jAccountsView

from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver

from typing import AsyncGenerator

class Neo4jViewsHolder(AbstractViewsHolder):

    def __init__(
            self,
            accounts: Neo4jAccountsView,
            germplasm: Neo4jGermplasmView,
            location_trees: Neo4jLocationTreesView,
            datasets: Neo4jDatasetsView,
            ontology: Neo4jOntologyView,
            units: Neo4jUnitsView,
            programs: Neo4jProgramsView,
            layout_trees: Neo4jLayoutTreesView,
            references: Neo4jReferencesView,
            people: Neo4jPeopleView,
            controls: Neo4jControlsView
    ):
        self.units = units
        self.programs = programs
        self.layout_trees = layout_trees
        self.ontology = ontology
        self.accounts = accounts
        self.location_trees = location_trees
        self.datasets = datasets
        self.germplasm = germplasm
        self.references = references
        self.people = people
        self.controls = controls


class Neo4jViewsFactory(AbstractViewsFactory):
    def __init__(
            self,
            state_store: AbstractStateStore,
            driver: Neo4jAsyncDriver
    ):
        super().__init__(driver, state_store)
        self.driver = driver

    @asynccontextmanager
    async def _get_views(self, user_id: int|None = None) -> AsyncGenerator[Neo4jViewsHolder, None]:
        async with self.driver.session() as session:
            accounts_view = Neo4jAccountsView(session=session, user_id=user_id)
            read_teams = await accounts_view.get_read_teams()
            yield Neo4jViewsHolder(
                ontology = Neo4jOntologyView(session=session),
                accounts = accounts_view,
                germplasm = Neo4jGermplasmView(session=session, user_id=user_id, read_teams=read_teams),
                location_trees = Neo4jLocationTreesView(state_store=self.state_store, user_id = user_id, read_teams=read_teams, session=session),
                datasets = Neo4jDatasetsView(user_id=user_id, read_teams=read_teams, session=session),
                units = Neo4jUnitsView(session=session, user_id=user_id, read_teams=read_teams),
                programs = Neo4jProgramsView(session=session, user_id=user_id, read_teams=read_teams),
                layout_trees = Neo4jLayoutTreesView(session=session, user_id=user_id, read_teams=read_teams),
                references = Neo4jReferencesView(session=session, user_id=user_id, read_teams=read_teams),
                people = Neo4jPeopleView(session=session, user_id=user_id, read_teams=read_teams),
                controls = Neo4jControlsView(session=session, user_id=user_id, read_teams=read_teams, accounts=accounts_view)
            )
