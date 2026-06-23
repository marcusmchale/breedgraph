
from src.breedgraph.domain.model.people import PersonInput
from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.utilities.inputs import LoremTextGenerator, UserInputGenerator

class PersonBuilder:
    user_input_generator = UserInputGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def person_input(cls, team_id: int|None = None):
        person_input = cls.user_input_generator.new_user_input()
        return PersonInput(
            name=person_input['name'],
            fullname=person_input['name'],
            email=person_input['email'],
            teams=[team_id] if team_id else []
        )

    async def person(self, user_id: int) -> int:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            person = await uow.repositories.people.create(
                self.person_input()
            )
            await uow.commit()
        return person.id