from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.people import (
    PersonBase, PersonStored
)
from src.breedgraph.domain.model.ontology import Term
from src.breedgraph.custom_exceptions import (
    IdentityExistsError,
    UnauthorisedOperationError,
    ProtectedNodeError
)

import logging


logger = logging.getLogger(__name__)

async def add_person(
        cmd: commands.people.CreatePerson,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        person = PersonBase(**cmd.model_dump())
        await uow.people.create(person)
        await uow.commit()