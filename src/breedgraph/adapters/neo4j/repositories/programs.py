import logging

from neo4j import AsyncResult, Record

from src.breedgraph.domain.model.programs import (
    StudyInput, StudyStored, TrialInput, TrialStored, ProgramInput, ProgramStored
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.service_layer.tracking import TrackableProtocol
from src.breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator, List

logger = logging.getLogger(__name__)

class Neo4jProgramsRepository(Neo4jControlledRepository[ProgramInput, ProgramStored]):

    async def _create_controlled(self, program: ProgramInput) -> ProgramStored:
        async for existing_program in self._get_all_controlled():
            if program.name.casefold() == existing_program.name.casefold():
                raise ValueError("A program with this name is already registered")

        stored_program = await self._create_program(program)
        return stored_program

    async def _create_program(self, program: ProgramInput) -> ProgramStored:
        logger.debug(f"Create program: {program}")
        result: AsyncResult = await self.tx.run(queries['programs']['create_program'], **program.model_dump())
        record: Record = await result.single()
        return ProgramStored(**record['program'])

    async def _create_trial(self, trial: TrialInput, program_id: int) -> TrialStored:
        logger.debug(f"Create trial: {trial}")
        result: AsyncResult = await self.tx.run(
            queries['programs']['create_trial'],
            **trial.model_dump(),
            program_id=program_id
        )
        record: Record = await result.single()
        return TrialStored(**record['trial'])

    async def _create_study(self, study: StudyInput, trial_id: int) -> StudyStored:
        logger.debug(f"Create study: {study}")
        result: AsyncResult = await self.tx.run(
            queries['programs']['create_study'],
            **study.model_dump(),
            trial_id=trial_id
        )
        record: Record = await result.single()
        return StudyStored(**record['study'])

    async def _update_program(self, program: ProgramStored):
        logger.debug(f"Set program: {program}")
        params=program.model_dump()
        params.pop('trials')
        await self.tx.run(queries['programs']['set_program'], params)

    async def _update_trial(self, trial: TrialStored):
        logger.debug(f"Set trial: {trial}")
        params = trial.model_dump()
        params.pop('studies')
        await self.tx.run(queries['programs']['set_trial'], params)

    async def _update_study(self, study: StudyStored):
        logger.debug(f"Set study: {study}")
        await self.tx.run(queries['programs']['set_study'], study.model_dump())

    async def _delete_trials(self, trial_ids: List[int]) -> None:
        logger.debug(f"Remove trials: {trial_ids}")
        await self.tx.run(queries['programs']['remove_trials'], trial_ids=trial_ids)

    async def _delete_studies(self, study_ids: List[int]) -> None:
        logger.debug(f"Remove studies: {study_ids}")
        await self.tx.run(queries['programs']['remove_studies'], study_ids=study_ids)

    @staticmethod
    def record_to_program(program: dict):
        for trial in program['trials']:
            trial['studies'] = {
                study['id']: StudyStored(**study) for study in trial['studies']
            }
        program['trials'] = {
            trial['id']: TrialStored(**trial) for trial in program['trials']
        }
        return ProgramStored(**program)

    async def _get_controlled(
            self,
            name: str = None,
            program_id: int = None,
            trial_id: int=None,
            study_id:int=None
    ) -> ProgramStored | None:
        if program_id is not None:
            result: AsyncResult = await self.tx.run( queries['programs']['read_program'], program_id=program_id)
        elif trial_id is not None:
            result: AsyncResult = await self.tx.run(queries['programs']['read_program_from_trial'], trial_id=trial_id)
        elif study_id is not None:
            result: AsyncResult = await self.tx.run(queries['programs']['read_program_from_study'], study_id=study_id)
        elif name is not None:
            result: AsyncResult = await self.tx.run(queries['programs']['read_program_by_name'], name_lower=name.casefold())
        else:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

        record = await result.single()

        if record:
            return self.record_to_program(record.get('program'))
        return None

    async def _get_all_controlled(self) -> AsyncGenerator[ProgramStored, None]:
        result: AsyncResult = await self.tx.run(queries['programs']['read_programs'])
        async for record in result:
            yield self.record_to_program(record.get('program'))

    async def _remove_controlled(self, program: ProgramStored) -> None:
        await self._delete_trials(list(program.trials.keys()))

    async def _update_controlled(self, program: TrackableProtocol | ProgramStored):
        if 'trials' in program.changed:
            for trial_id in program.trials.added:
                trial = program.trials[trial_id]
                if isinstance(trial, TrialInput):
                    stored_trial = await self._create_trial(trial, program.id)
                    program.trials.replace_with_stored(trial_id, stored_trial)
                else:
                    raise ValueError("only new trials may be added to a program")
            for trial_id in program.trials.changed:
                trial = program.trials[trial_id]

                if 'studies' in trial.changed:
                    for study_id in trial.studies.added:
                        study = trial.studies[study_id]
                        if isinstance(study, StudyInput):
                            stored_study = await self._create_study(study, trial_id)
                            trial.studies.replace_with_stored(study_id, stored_study)
                        else:
                            raise ValueError("only new studies may be added to a trial")
                    for study_id in trial.studies.changed:
                        study = trial.studies[study_id]
                        if isinstance(study, StudyStored):
                            await self._update_study(study)
                        else:
                            raise ValueError("only stored studies have tracked changes")
                    if trial.studies.removed:
                        await self._delete_studies(trial.studies.removed)

                if isinstance(trial, TrialStored):
                    await self._update_trial(trial)
                else:
                    raise ValueError("Only stored trials have tracked changes")

            if program.trials.removed:
                await self._delete_trials(program.trials.removed)

        if program.changed - {'trials', 'controller'}:
            await self._update_program(program)




