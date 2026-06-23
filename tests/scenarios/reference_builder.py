from src.breedgraph.domain.model.references import LegalReference, FileReferenceInput
from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.utilities.inputs import LoremTextGenerator
import uuid

class ReferenceBuilder:
    text_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def legal_reference_input(cls):
        return LegalReference(text=cls.text_generator.new_text(100))

    @classmethod
    def file_reference_input(cls):
        return FileReferenceInput(
            description=cls.text_generator.new_text(20),
            filename=cls.text_generator.new_text(5),
            file_id=uuid.uuid4().hex
        )


