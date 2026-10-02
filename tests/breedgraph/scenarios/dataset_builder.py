
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.ontology import ScaleStored
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.breedgraph.utilities.inputs import LoremTextGenerator

from typing import Dict

class DatasetBuilder:
    text_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def dataset_input(cls, concept_id: int, study_id: int):
        return DatasetInput(
            concept=concept_id,
            study=study_id
        )

    @classmethod
    def record_input(cls, unit_id: int, value):
        return DataRecordInput(unit=unit_id, value=value)

    async def dataset(
            self,
            user_id: int,
            concept_id: int,
            study_id: int
    ) -> Dict[str, int]:
        async with (self.uow_factory.get_uow(user_id=user_id) as uow):
            dataset = await uow.repositories.datasets.create(
                self.dataset_input(concept_id=concept_id, study_id=study_id)
            )
            await uow.commit()

        return {
            'dataset_id': dataset.id
        }


