"""
The licence gate (docs/licences.md §5): a dataset's records and dimensions, analyses of it and the files citing it
are given only to requests carrying an acceptance of its study's licence's current text, unless the user is exempt,
reading the dataset or its study through a controlling team
"""
from typing import Iterable

from breedgraph.custom_exceptions import LicenceNotAcceptedError
from breedgraph.service_layer.queries.read_models import DatasetRead
from breedgraph.entrypoints.fastapi.graphql.acceptances import request_acceptances
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import update_reference_map


async def licences_not_accepted(context, licence_ids: Iterable[int]) -> list[int]:
    """Of these licences, those the request carries no acceptance of at their current text"""
    licence_ids = sorted(set(licence_ids))
    if not licence_ids:
        return []
    await update_reference_map(context, reference_ids=licence_ids)
    references = context['reference_map']
    acceptances = request_acceptances(context)
    return [
        licence_id for licence_id in licence_ids
        if not acceptances.accepts_licence(licence_id, getattr(references.get(licence_id), 'content_hash', None))
    ]


async def require_licence_accepted(context, dataset: DatasetRead) -> None:
    """Refuse the dataset's data unless the user is exempt from its licence or has accepted it"""
    if dataset.redacted or not dataset.licence_required:
        return
    if await licences_not_accepted(context, [dataset.licence]):
        raise LicenceNotAcceptedError(
            f"The data of dataset {dataset.id} needs its study's licence, reference {dataset.licence}, accepted: "
            f"read it, and accept it with licencesAccept"
        )
