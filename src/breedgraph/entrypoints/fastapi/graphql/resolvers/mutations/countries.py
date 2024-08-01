from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.regions import (
    GeoCoordinate, AddLocation
)

from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

from typing import List

import logging
logger = logging.getLogger(__name__)


@graphql_mutation.field("add_location")
@graphql_payload
async def add_location(
        _,
        info,
        user: int,
        name: str,
        type: int,
        fullname: str = None,
        description: str = None,
        code: str = None,
        address: str = None,
        coordinates: List[GeoCoordinate] = None,
        parent: int | None = None
) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {account.user.id} adds team: {name}")
    cmd = AddLocation(
        user=account.user.id,
        name=name,
        type=type,
        fullname=fullname,
        description=description,
        code=code,
        address=address,
        coordinates=coordinates
    )
    await info.context['bus'].handle(cmd)
    return True
