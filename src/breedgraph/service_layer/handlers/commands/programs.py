from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory

from src.breedgraph.domain import commands
from src.breedgraph.domain.model.programs import (
    ProgramInput, ProgramStored,
    TrialInput, TrialStored,
    StudyInput, StudyStored
)
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    UnauthorisedOperationError
)

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

# Program Handlers
@handlers.command_handler()
async def create_program(
        cmd: commands.programs.CreateProgram,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        # Check if a program with the same name already exists
        existing_program = await uow.repositories.programs.get(name=cmd.name)
        if existing_program is not None:
            raise IdentityExistsError(f"Program with name '{cmd.name}' already exists")

        program = ProgramInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            description=cmd.description,
            contact_ids=cmd.contact_ids,
            reference_ids=cmd.reference_ids
        )
        await uow.repositories.programs.create(program)
        await uow.commit()

@handlers.command_handler()
async def update_program(
        cmd: commands.programs.UpdateProgram,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        program = await uow.repositories.programs.get(program_id=cmd.program_id)
        if program is None:
            raise NoResultFoundError(f"Program with ID {cmd.program_id} not found")

        # Check if updating name would create a conflict
        if cmd.name is not None and cmd.name != program.name:
            existing_program = await uow.repositories.programs.get(name=cmd.name)
            if existing_program is not None and existing_program.id != cmd.program:
                raise IdentityExistsError(f"Program with name '{cmd.name}' already exists")

        # Update fields that are provided
        if cmd.name is not None:
            program.name = cmd.name
        if cmd.fullname is not None:
            program.fullname = cmd.fullname
        if cmd.description is not None:
            program.description = cmd.description
        if cmd.contact_ids is not None:
            program.contact_ids = cmd.contact_ids
        if cmd.reference_ids is not None:
            program.reference_ids = cmd.reference_ids

        await uow.commit()

@handlers.command_handler()
async def delete_program(
        cmd: commands.programs.DeleteProgram,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:

        program = await uow.repositories.programs.get(program_id=cmd.program_id)
        if program is None:
            raise NoResultFoundError(f"Program with ID {cmd.program_id} not found")
        await uow.repositories.programs.remove(program)
        await uow.commit()


# Trial Handlers
@handlers.command_handler()
async def create_trial(
        cmd: commands.programs.CreateTrial,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        program = await uow.repositories.programs.get(program_id=cmd.program_id)
        if program is None:
            raise NoResultFoundError(f"Program with ID {cmd.program} not found")

        trial = TrialInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            description=cmd.description,
            start=cmd.start,
            end=cmd.end,
            contact_ids=cmd.contact_ids,
            reference_ids=cmd.reference_ids
        )
        program.add_trial(trial)
        await uow.commit()

@handlers.command_handler()
async def update_trial(
        cmd: commands.programs.UpdateTrial,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        program = await uow.repositories.programs.get(trial_id=cmd.trial_id)
        if program is None:
            raise NoResultFoundError(f"Program with ID {cmd.program} not found")

        trial = program.trials.get(cmd.trial_id)
        if trial is None:
            raise NoResultFoundError(f"Trial with ID {cmd.trial_id} not found")

        # Update fields that are provided
        if cmd.name is not None:
            trial.name = cmd.name
        if cmd.fullname is not None:
            trial.fullname = cmd.fullname
        if cmd.description is not None:
            trial.description = cmd.description
        if cmd.start is not None:
            trial.start = cmd.start
        if cmd.end is not None:
            trial.end = cmd.end
        if cmd.contact_ids is not None:
            trial.contact_ids = cmd.contact_ids
        if cmd.reference_ids is not None:
            trial.reference_ids = cmd.reference_ids

        await uow.commit()

@handlers.command_handler()
async def delete_trial(
        cmd: commands.programs.DeleteTrial,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        program = await uow.repositories.programs.get(trial_id=cmd.trial_id)
        if program is None:
            raise NoResultFoundError(f"Program containing trial with ID {cmd.trial_id} not found")
        trial = program.trials.get(cmd.trial_id)
        # Check if trial has studies that should prevent deletion
        if hasattr(trial, 'studies') and trial.studies:
            raise UnauthorisedOperationError("Cannot delete trial that contains studies")
        program.remove_trial(trial)
        await uow.commit()


# Study Handlers
@handlers.command_handler()
async def create_study(
        cmd: commands.programs.CreateStudy,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        program = await uow.repositories.programs.get(trial_id=cmd.trial_id)
        if program is None:
            raise NoResultFoundError(f"Program with trial ID {cmd.trial_id} not found")

        trial = program.trials.get(cmd.trial_id)
        study = StudyInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            description=cmd.description,
            practices=cmd.practices,
            start=cmd.start,
            end=cmd.end,
            dataset_ids=cmd.dataset_ids,
            design_id=cmd.design_id,
            licence_id=cmd.licence_id,
            reference_ids=cmd.reference_ids
        )
        trial.add_study(study)
        await uow.commit()

@handlers.command_handler()
async def update_study(
        cmd: commands.programs.UpdateStudy,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        program = await uow.repositories.programs.get(study_id=cmd.study_id)
        if program is None:
            raise NoResultFoundError(f"Program containing study with ID {cmd.study} not found")

        study = program.get_study(cmd.study_id)

        # Update fields that are provided
        if cmd.name is not None:
            study.name = cmd.name
        if cmd.fullname is not None:
            study.fullname = cmd.fullname
        if cmd.description is not None:
            study.description = cmd.description
        if cmd.practices is not None:
            study.practices = cmd.practices
        if cmd.start is not None:
            study.start = cmd.start
        if cmd.end is not None:
            study.end = cmd.end
        if cmd.dataset_ids is not None:
            study.dataset_ids = cmd.dataset_ids
        if cmd.design_id is not None:
            study.design_id = cmd.design_id
        if cmd.licence_id is not None:
            study.licence_id = cmd.licence_id
        if cmd.reference_ids is not None:
            study.reference_ids = cmd.reference_ids
        await uow.commit()

@handlers.command_handler()
async def delete_study(
        cmd: commands.programs.DeleteStudy,
        uow: AbstractUnitOfWorkFactory
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        program = await uow.repositories.programs.get(study_id=cmd.study_id)
        if program is None:
            raise NoResultFoundError(f"Program containing study with ID {cmd.study_id} not found")
        study = program.get_study(cmd.study_id)
        program.remove_study(study)
        await uow.commit()