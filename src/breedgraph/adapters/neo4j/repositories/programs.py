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
        program_data = program.model_dump()
        contact_ids = program_data.pop('contact_ids')
        reference_ids = program_data.pop('reference_ids')
        result: AsyncResult = await self.tx.run(
            queries['programs']['create_program'],
            program_data = program_data,
            contact_ids = contact_ids,
            reference_ids = reference_ids
        )
        record: Record = await result.single()
        return self.record_to_program(record)

    async def _create_trial(self, trial: TrialInput, program_id: int) -> TrialStored:
        logger.debug(f"Create trial: {trial}")
        trial_data = trial.model_dump()
        self.serialize_dt64(trial_data, to_neo4j=True)
        contact_ids = trial_data.pop('contact_ids')
        reference_ids = trial_data.pop('reference_ids')
        result: AsyncResult = await self.tx.run(
            queries['programs']['create_trial'],
            trial_data = trial_data,
            contact_ids = contact_ids,
            reference_ids = reference_ids,
            program_id=program_id
        )
        record: Record = await result.single()
        return self.record_to_trial(record)

    async def _create_study(self, study: StudyInput, trial_id: int) -> StudyStored:
        logger.debug(f"Create study: {study}")
        study_data = study.model_dump()
        self.serialize_dt64(study_data, to_neo4j=True)
        reference_ids = study_data.pop('reference_ids')
        licence_id = study_data.pop('licence_id')
        dataset_ids = study_data.pop('dataset_ids')
        design_id = study_data.pop('design_id')
        result: AsyncResult = await self.tx.run(
            queries['programs']['create_study'],
            study_data=study_data,
            reference_ids = reference_ids,
            licence_id = licence_id,
            dataset_ids = dataset_ids,
            design_id = design_id,
            trial_id=trial_id
        )
        record: Record = await result.single()
        return self.record_to_study(record)

    async def _update_program(self, program: ProgramStored):
        logger.debug(f"Set program: {program}")
        program_data = program.model_dump()
        program_data.pop('trials')
        program_id = program_data.pop('id')
        contact_ids = program_data.pop('contact_ids')
        reference_ids = program_data.pop('reference_ids')
        await self.tx.run(
            queries['programs']['set_program'],
            program_id=program_id,
            program_data=program_data,
            contact_ids=contact_ids,
            reference_ids=reference_ids
        )

    async def _update_trial(self, trial: TrialStored):
        logger.debug(f"Set trial: {trial}")
        trial_data = trial.model_dump()
        trial_data.pop('studies')
        self.serialize_dt64(trial_data, to_neo4j=True)
        trial_id = trial_data.pop('id')
        contact_ids = trial_data.pop('contact_ids')
        reference_ids = trial_data.pop('reference_ids')
        await self.tx.run(
            queries['programs']['set_trial'],
            trial_id=trial_id,
            trial_data=trial_data,
            contact_ids=contact_ids,
            reference_ids=reference_ids
        )

    async def _update_study(self, study: StudyStored):
        logger.debug(f"Set study: {study}")
        study_data = study.model_dump()
        self.serialize_dt64(study_data, to_neo4j=True)
        study_id = study_data.pop('id')
        reference_ids = study_data.pop('reference_ids')
        licence_id = study_data.pop('licence_id')
        dataset_ids = study_data.pop('dataset_ids')
        design_id = study_data.pop('design_id')

        await self.tx.run(
            queries['programs']['set_study'],
            study_id = study_id,
            study_data=study_data,
            reference_ids=reference_ids,
            licence_id=licence_id,
            dataset_ids=dataset_ids,
            design_id=design_id
        )

    async def _delete_trials(self, trial_ids: List[int]) -> None:
        logger.debug(f"Remove trials: {trial_ids}")
        await self.tx.run(queries['programs']['remove_trials'], trial_ids=trial_ids)

    async def _delete_studies(self, study_ids: List[int]) -> None:
        logger.debug(f"Remove studies: {study_ids}")
        await self.tx.run(queries['programs']['remove_studies'], study_ids=study_ids)

    def record_to_study(self, record: Record | dict) -> StudyStored:
        if isinstance(record, Record):
            record = record.data()
        if 'study' in record:
            record = record.get('study')
        record = self.deserialize_dt64(record)
        return StudyStored(**record)

    def record_to_trial(self, record: Record | dict) -> TrialStored:
        if isinstance(record, Record):
            record = record.data()
        if 'trial' in record:
            record = record.get('trial')
        record = self.deserialize_dt64(record)

        if 'studies' in record:
            record['studies'] = {
                study['id']: self.record_to_study(study) for study in record['studies']
            }
        return TrialStored(**record)

    def record_to_program(self, record: Record | dict) -> ProgramStored:
        if isinstance(record, Record):
            record = record.data()
        if 'program' in record:
            record = record.get('program')

        if 'trials' in record:
            record['trials'] = {
                trial['id']: self.record_to_trial(trial) for trial in record['trials']
            }
        return ProgramStored(**record)

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
        await self.tx.run(queries['programs']['remove_programs'], program_ids=[program.id])

    async def _update_controlled(self, program: TrackableProtocol | ProgramStored):
        if 'trials' in program.changed:
            for trial_id in program.trials.added.copy():
                trial = program.trials[trial_id]
                if isinstance(trial, TrialInput):
                    stored_trial = await self._create_trial(trial, program.id)
                    program.trials.replace_with_stored(trial_id, stored_trial)
                else:
                    raise ValueError("only new trials may be added to a program")
            for trial_id in program.trials.changed.copy():
                trial = program.trials[trial_id]

                if 'studies' in trial.changed:
                    for study_id in trial.studies.added.copy():
                        study = trial.studies[study_id]
                        if isinstance(study, StudyInput):
                            stored_study = await self._create_study(study, trial_id)
                            trial.studies.replace_with_stored(study_id, stored_study)
                        else:
                            raise ValueError("only new studies may be added to a trial")
                    for study_id in trial.studies.changed.copy():
                        study = trial.studies[study_id]
                        if isinstance(study, StudyStored):
                            await self._update_study(study)
                        else:
                            raise ValueError("only stored studies have tracked changes")
                    if trial.studies.removed:
                        await self._delete_studies(list(trial.studies.removed.keys()))

                if isinstance(trial, TrialStored) and trial.changed - {'studies'}:
                    await self._update_trial(trial)

            if program.trials.removed:
                await self._delete_trials(list(program.trials.removed.keys()))

        if program.changed - {'trials', 'controller'}:
            await self._update_program(program)




