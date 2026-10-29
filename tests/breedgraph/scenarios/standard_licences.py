"""
The standard licences the test setup seeds (docs/licences.md §6), for scenarios to give the studies they release: a
study released beyond private, or with a dataset released beyond private, has a licence (docs/licences.md §1)
"""
from breedgraph.service_layer.application.licence_seed import CC_BY
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory


async def standard_licence_id(uow_factory: AbstractUnitOfWorkFactory, seed_key: str = CC_BY) -> int:
    async with uow_factory.get_uow() as uow:
        return await uow.repositories.references.get_seeded_id(seed_key)
