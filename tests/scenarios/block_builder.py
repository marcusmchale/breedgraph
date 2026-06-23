
from src.breedgraph.domain.model.blocks import UnitInput
from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.utilities.inputs import LoremTextGenerator

class BlockBuilder:
    text_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def unit_input(cls):
        return UnitInput(name=cls.text_generator.new_text(10))

    async def unit(self, user_id: int) -> int:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            block = await uow.repositories.blocks.create(self.unit_input())
            await uow.commit()
        return block.root.id