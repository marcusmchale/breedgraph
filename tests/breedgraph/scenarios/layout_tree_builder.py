from breedgraph.domain.model.layout_trees import LayoutInput

from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.breedgraph.utilities.inputs import LoremTextGenerator

from typing import Dict

class LayoutTreeBuilder:
    text_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    async def layout_tree(
            self,
            user_id: int,
            team_id: int,
            location_id: int,
            ontology_layout_named:int,
            ontology_layout_3d:int,
            ontology_layout_grid: int
    ) -> Dict[str, int|str|None]:

        async with self.uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
            facility_layout_input = LayoutInput(
                name="Growth Facility",
                type=ontology_layout_named,
                location=location_id,
                axes=["Chamber"]
            )
            layout_tree = await uow.repositories.layout_trees.create(facility_layout_input)
            chamber_layout_input = LayoutInput(
                name="Chamber 1",
                type=ontology_layout_3d,
                axes=["Depth", "Vertical", "Horizontal"]
            )
            chamber_temp_id = layout_tree.add_layout(chamber_layout_input, parent_id=layout_tree.root.id, position=["1"])
            shelf_layout_input = LayoutInput(
                name="Shelf 1",
                type=ontology_layout_grid,
                axes=["Column", "Row"]
            )
            layout_tree.add_layout(
                shelf_layout_input,
                parent_id = chamber_temp_id,
                position=["rear", "top", "right"]
            )
            await uow.commit()

        facility_layout = layout_tree.root
        assert facility_layout
        descendants = layout_tree.get_descendants(facility_layout.id)
        chamber_layout = layout_tree.get_layout(descendants[0])
        shelf_layout = layout_tree.get_layout(descendants[1])

        return {
            'layout_facility_id': facility_layout.id,
            'layout_facility_name': facility_layout.name,
            'layout_chamber_id': chamber_layout.id,
            'layout_chamber_name': chamber_layout.name,
            'layout_shelf_id': shelf_layout.id,
            'layout_shelf_name': shelf_layout.name
        }


