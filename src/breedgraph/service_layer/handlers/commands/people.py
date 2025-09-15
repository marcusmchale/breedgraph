from src.breedgraph.domain import commands
from src.breedgraph.domain.model.people import (
    PersonBase, PersonStored
)

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def add_person(
        cmd: commands.people.CreatePerson,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow() as uow:
        person = PersonBase(**cmd.model_dump())
        await uow.repositories.people.create(person)
        await uow.commit()