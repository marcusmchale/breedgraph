from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.accounts import (
    Authorisation, Access,
    Affiliation,
)
from src.breedgraph.domain.model.ontologies import Term
from src.breedgraph.custom_exceptions import (
    IdentityExistsError,
    UnauthorisedOperationError,
    ProtectedNodeError
)

import logging


logger = logging.getLogger(__name__)

async def add_term(
        cmd: commands.ontologies.AddTerm,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        term = Term(
            name = cmd.name,
            description = cmd.description,
            abbreviation = cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list(),
            parents=cmd.parents if cmd.parents is not None else list(),
        )
        ontology.add_entry(term)
        await uow.commit()