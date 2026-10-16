
from breedgraph.domain.model.unit_graphs import UnitInput
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.breedgraph.utilities.inputs import LoremTextGenerator

class UnitGraphBuilder:
    text_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def unit_input(cls, germplasm_id: int | None = None):
        return UnitInput(name=cls.text_generator.new_text(10), germplasm=germplasm_id)

    async def unit(self, user_id: int, team_id: int, germplasm_id: int | None = None) -> int:
        async with self.uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
            unit_graph = await uow.repositories.unit_graphs.create(self.unit_input(germplasm_id))
            await uow.commit()
        return unit_graph.root.id