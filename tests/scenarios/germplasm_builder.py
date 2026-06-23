from src.breedgraph.domain.model.germplasm import GermplasmInput, GermplasmRelationship, GermplasmSourceType
from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.utilities.inputs import LoremTextGenerator

class GermplasmBuilder:
    text_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def germplasm_input(cls) -> GermplasmInput:
        return GermplasmInput(
            name=cls.text_generator.new_text(10),
            description=cls.text_generator.new_text(20)
        )

    @classmethod
    def relationship_input(
            cls,
            source_id,
            sink_id
    ) -> GermplasmRelationship:
        return GermplasmRelationship(
            source_id=source_id,
            sink_id=sink_id
        )

    async def germplasm(self, user_id: int) -> int:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            germplasm = await uow.germplasm.create_entry(self.germplasm_input())
            await uow.commit()
            return germplasm.id

