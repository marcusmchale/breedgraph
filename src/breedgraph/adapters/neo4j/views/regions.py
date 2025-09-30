from neo4j import AsyncTransaction, AsyncResult
from typing import AsyncGenerator

from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService
from src.breedgraph.service_layer.queries.views.regions import AbstractRegionsViews
from src.breedgraph.domain.model.controls import ControlledModelLabel

from src.breedgraph.domain.model.regions import LocationOutput
from src.breedgraph.domain.model.controls import Access

from src.breedgraph.adapters.neo4j.cypher import queries

class Neo4jRegionsViews(AbstractRegionsViews):
    def __init__(
            self,
            tx: AsyncTransaction,
            access_control: AbstractAccessControlService,
    ):
        self.tx = tx
        self.access_control = access_control

    async def get_locations_by_type(self, location_type_id: int) -> AsyncGenerator[LocationOutput, None]:
        # First get all locations of this type
        result: AsyncResult = await self.tx.run(queries['regions']['get_locations_by_type'], location_type=location_type_id)

        # collect these for filtering
        locations_map = {}
        async for record in result:
            location_output = LocationOutput(**record['location'])
            locations_map[location_output.id] = location_output

        # Retrieve controllers for these
        controllers = await self.access_control.get_controllers(
            label=ControlledModelLabel.LOCATION,
            model_ids=list(locations_map.keys())
        )
        read_teams = self.access_control.access_teams.get(Access.READ, set())
        user_id = self.access_control.user_id

        # Filter and yield based on access control
        for location_id, location_output in locations_map.items():
            controller = controllers.get(location_id)
            if controller and controller.has_access(Access.READ, user_id, read_teams):
                yield location_output
            else:
                continue