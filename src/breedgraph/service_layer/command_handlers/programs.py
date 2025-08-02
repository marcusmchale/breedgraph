from src.breedgraph.service_layer import unit_of_work
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

import logging

logger = logging.getLogger(__name__)


# Program Handlers
async def create_program(
        cmd: commands.programs.CreateProgram,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user, release=ReadRelease[cmd.release]) as uow:
        # Check if a program with the same name already exists
        existing_program = await uow.programs.get(name=cmd.name)


        if existing_program is not None:
            raise IdentityExistsError(f"Program with name '{cmd.name}' already exists")

        program = ProgramInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            description=cmd.description,
            contacts=cmd.contacts,
            references=cmd.references
        )

        await uow.programs.create(program)
        await uow.commit()


async def update_program(
        cmd: commands.programs.UpdateProgram,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user) as uow:
        program = await uow.programs.get(id=cmd.program)
        if program is None:
            raise NoResultFoundError(f"Program with ID {cmd.program} not found")

        # Check if updating name would create a conflict
        if cmd.name is not None and cmd.name != program.name:
            existing_program = await uow.programs.get(name=cmd.name)
            if existing_program is not None and existing_program.id != cmd.program:
                raise IdentityExistsError(f"Program with name '{cmd.name}' already exists")

        # Update fields that are provided
        if cmd.name is not None:
            program.name = cmd.name
        if cmd.fullname is not None:
            program.fullname = cmd.fullname
        if cmd.description is not None:
            program.description = cmd.description
        if cmd.contacts is not None:
            program.contacts = cmd.contacts
        if cmd.references is not None:
            program.references = cmd.references
        if cmd.release is not None:
            # Update the release level for the program
            # Note: This assumes the program has access control and the user has appropriate permissions
            program.set_release(team_id=None, release=ReadRelease[cmd.release])

        await uow.commit()


async def delete_program(
        cmd: commands.programs.DeleteProgram,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user) as uow:

        program = await uow.programs.get(program_id=cmd.program)
        if program is None:
            raise NoResultFoundError(f"Program with ID {cmd.program} not found")

        await uow.programs.remove(program)
        await uow.commit()


# Trial Handlers
async def create_trial(
        cmd: commands.programs.CreateTrial,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user, release=ReadRelease[cmd.release]) as uow:
        program = await uow.programs.get(id=cmd.program)
        if program is None:
            raise NoResultFoundError(f"Program with ID {cmd.program} not found")

        trial = TrialInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            description=cmd.description,
            start=cmd.start,
            end=cmd.end,
            contacts=cmd.contacts,
            references=cmd.references
        )

        program.add_trial(trial)
        await uow.commit()


async def update_trial(
        cmd: commands.programs.UpdateTrial,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user) as uow:
        trial = await uow.trials.get(id=cmd.trial)
        if trial is None:
            raise NoResultFoundError(f"Trial with ID {cmd.trial} not found")

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
        if cmd.contacts is not None:
            trial.contacts = cmd.contacts
        if cmd.references is not None:
            trial.references = cmd.references
        if cmd.release is not None:
            # Update the release level for the trial
            trial.set_release(team_id=None, release=ReadRelease[cmd.release])

        await uow.commit()


async def delete_trial(
        cmd: commands.programs.DeleteTrial,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user) as uow:
        trial = await uow.trials.get(id=cmd.trial)
        if trial is None:
            raise NoResultFoundError(f"Trial with ID {cmd.trial} not found")

        # Check if trial has studies that would prevent deletion
        if hasattr(trial, 'studies') and trial.studies:
            raise UnauthorisedOperationError("Cannot delete trial that contains studies")

        await uow.trials.remove(trial)
        await uow.commit()


# Study Handlers
async def create_study(
        cmd: commands.programs.CreateStudy,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user, release=ReadRelease[cmd.release]) as uow:
        trial = await uow.trials.get(id=cmd.trial)
        if trial is None:
            raise NoResultFoundError(f"Trial with ID {cmd.trial} not found")

        study = StudyInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            description=cmd.description,
            external_id=cmd.external_id,
            practices=cmd.practices,
            start=cmd.start,
            end=cmd.end,
            factors=cmd.factors,
            observations=cmd.observations,
            design=cmd.design,
            licence=cmd.licence,
            references=cmd.references
        )

        trial.add_study(study)
        await uow.commit()


async def update_study(
        cmd: commands.programs.UpdateStudy,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user) as uow:
        study = await uow.studies.get(id=cmd.study)
        if study is None:
            raise NoResultFoundError(f"Study with ID {cmd.study} not found")

        # Update fields that are provided
        if cmd.name is not None:
            study.name = cmd.name
        if cmd.fullname is not None:
            study.fullname = cmd.fullname
        if cmd.description is not None:
            study.description = cmd.description
        if cmd.external_id is not None:
            study.external_id = cmd.external_id
        if cmd.practices is not None:
            study.practices = cmd.practices
        if cmd.start is not None:
            study.start = cmd.start
        if cmd.end is not None:
            study.end = cmd.end
        if cmd.factors is not None:
            study.factors = cmd.factors
        if cmd.observations is not None:
            study.observations = cmd.observations
        if cmd.design is not None:
            study.design = cmd.design
        if cmd.licence is not None:
            study.licence = cmd.licence
        if cmd.references is not None:
            study.references = cmd.references
        if cmd.release is not None:
            # Update the release level for the study
            study.set_release(team_id=None, release=ReadRelease[cmd.release])

        await uow.commit()


async def delete_study(
        cmd: commands.programs.DeleteStudy,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user) as uow:
        study = await uow.studies.get(id=cmd.study)
        if study is None:
            raise NoResultFoundError(f"Study with ID {cmd.study} not found")

        await uow.studies.remove(study)
        await uow.commit()