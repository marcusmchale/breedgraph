from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.domain.model.references import ReferenceType
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from breedgraph.entrypoints.fastapi.graphql.acceptances import request_acceptances, save_acceptances
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import update_reference_map

from . import graphql_mutation


@graphql_mutation.field("licencesAccept")
@graphql_payload
async def accept_licences(_, info, licences: list[dict]) -> bool:
    """
    Study licences accepted, each at the text read: all or none, refused for any that changed since or that the user
    can't read (docs/licences.md §5)
    """
    licence_ids = [int(licence['id']) for licence in licences]
    await update_reference_map(info.context, reference_ids=licence_ids)
    references = info.context['reference_map']
    acceptances = request_acceptances(info.context)
    for licence in licences:
        licence_id = int(licence['id'])
        reference = references.get(licence_id)
        if reference is None or reference.type != ReferenceType.LEGAL or reference.content_hash is None:
            raise NoResultFoundError(f"Licence {licence_id} was not found")
        if reference.content_hash != licence['content_hash']:
            raise ValueError(f"Licence {licence_id} has changed: please read it again")
        acceptances.accept_licence(licence_id, licence['content_hash'])
    save_acceptances(info.context, acceptances)
    return True
