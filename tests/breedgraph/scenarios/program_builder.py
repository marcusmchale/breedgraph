
from breedgraph.domain.model.programs import (
    ProgramInput, TrialInput, StudyInput, StudyStored,
    RecordGroupingInput, RecordGroupingStored,
    GroupingScope, DatasetScope
)
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.breedgraph.utilities.inputs import LoremTextGenerator

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
    def study_input(cls, replicate_type: int, batch_type: int, dataset_id: int|None=None):
        return StudyInput(
            name=cls.text_generator.new_text(10),
            groupings=[
                RecordGroupingInput(name='Study Scoped Batch',  type=batch_type, scope=GroupingScope.STUDY_WIDE),
                RecordGroupingInput(
                    name='Dataset Scoped Replicate',
                    type=replicate_type,
                    scope=GroupingScope.DATASET_SCOPED,
                    dataset_scopes=[DatasetScope(dataset_ids={dataset_id})] if dataset_id else []
                )
            ]
        )

    async def program_trial_study(self, user_id: int, replicate_type: int, batch_type: int) -> Dict[str, int|list[int|str]]:
        async with (self.uow_factory.get_uow(user_id=user_id) as uow):
            program = await uow.repositories.programs.create(self.program_input())
            program.add_trial(self.trial_input())
            await uow.repositories.programs.update_seen()
            trial_id = list(program.trials.keys())[0]
            study_input = self.study_input(replicate_type=replicate_type, batch_type=batch_type)
            program.add_study(trial_id=trial_id, study=study_input)
            await uow.repositories.programs.update_seen()
            study_id = list(program.get_trial(trial_id).studies.keys())[0]
            study: StudyStored = program.get_study(study_id)
            await uow.commit()

        return {
            'program_id': program.id,
            'trial_id': trial_id,
            'study_id': study_id,
            'grouping_ids': [grouping.id for grouping in study.groupings if isinstance(grouping, RecordGroupingStored)],
            'grouping_names': [grouping.name for grouping in study.groupings if isinstance(grouping, RecordGroupingStored)]
        }


