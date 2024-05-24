from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.people import (
    Person, PersonStored
)
from src.breedgraph.domain.model.ontologies import Term
from src.breedgraph.custom_exceptions import (
    IdentityExistsError,
    UnauthorisedOperationError,
    ProtectedNodeError
)

import logging


logger = logging.getLogger(__name__)

async def add_person(
        cmd: commands.people.AddPerson,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        person = Person(**cmd)
        await uow.people.create(person)
        await uow.commit()