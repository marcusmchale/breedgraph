from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.ontologies import (
    AddTerm
)
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

from typing import List

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("add_term")
@graphql_payload
async def add_term(
        _,
        info,
        name: str,
        description: str,
        abbreviation: str,
        synonyms: List[str],
        authors: List[int],
        references: List[int],
        parents: List[int]
) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {account.user.id} adds term: {name}")
    
    cmd = AddTerm(
        user=account.user.id,
        name=name,
        description=description,
        abbreviation=abbreviation,
        synonyms=synonyms,
        authors=authors,
        references=references,
        parents=parents
    )
    await info.context['bus'].handle(cmd)
    return True