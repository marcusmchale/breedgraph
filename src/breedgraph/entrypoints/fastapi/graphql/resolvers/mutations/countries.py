from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.countries import (
    AddCountry
)
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("add_country")
@graphql_payload
async def add_country(
        _,
        info,
        name: str,
        code: str
) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {account.user.id} adds team: {name}")
    cmd = AddCountry(
        admin=account.user.id,
        name=name,
        code=code
    )
    await info.context['bus'].handle(cmd)
    return True
