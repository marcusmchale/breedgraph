from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.utilities.inputs import LoremTextGenerator

from typing import Dict

class ProgramBuilder:
    text_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def program_input(cls):
        return ProgramInput(name=cls.text_generator.new_text(10))

    @classmethod
    def trial_input(cls):
        return TrialInput(name=cls.text_generator.new_text(10))

    @classmethod
    def study_input(cls):
        return StudyInput(name=cls.text_generator.new_text(10))

    async def program_trial_study(self, user_id: int) -> Dict[str, int]:
        async with (self.uow_factory.get_uow(user_id=user_id) as uow):
            program = await uow.repositories.programs.create(self.program_input())
            program.add_trial(self.trial_input())
            await uow.repositories.programs.update_seen()
            trial_id = list(program.trials.keys())[0]
            program.add_study(trial_id=trial_id, study=self.study_input())
            await uow.commit()

        study_id = list(program.get_trial(trial_id).studies.keys())[0]

        return {
            'program_id': program.id,
            'trial_id': trial_id,
            'study_id': study_id
        }


