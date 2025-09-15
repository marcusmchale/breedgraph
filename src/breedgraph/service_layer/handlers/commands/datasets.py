import tests.integration.conftest
from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from src.breedgraph.domain import commands
from src.breedgraph.domain.model.datasets import DataSetInput, DataSetStored, DataRecordInput
from src.breedgraph.domain.model.ontology import VariableStored, EventTypeStored, FactorStored, ScaleType

from src.breedgraph.domain.services.value_parsers import ValueParser

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def add_dataset(
        cmd: commands.datasets.CreateDataSet,
        uow: AbstractUnitOfWork
):
    kwargs = cmd.model_dump()
    async with uow.get_uow(user_id=kwargs.pop('user')) as uow:
        await uow.repositories.datasets.create(DataSetInput(**kwargs))
        await uow.commit()

@handlers.command_handler()
async def add_record(
        cmd: commands.datasets.AddRecord,
        uow: AbstractUnitOfWork
):
    kwargs = cmd.model_dump()
    async with uow.get_uow(user_id=kwargs.pop('user')) as uow:
        dataset: DataSetStored = await uow.repositories.datasets.get(dataset_id=kwargs.pop('dataset'))

        ontology_service = uow.ontology
        scale_id = ontology_service.get_scale_id(dataset.ontology_id)
        scale = ontology_service.get_entry(scale_id)
        if scale.scale_type in [ScaleType.ORDINAL, ScaleType.NOMINAL]:
            category_ids = ontology_service.get_category_ids(scale.id)
            categories = [ontology_service.get_entry(c) for c in category_ids]
        else:
            categories = None
        kwargs['value'] = ValueParser().parse(
            value=kwargs.get('value'),
            scale=scale,
            categories=categories,
            germplasm=uow.germplasm
        )
        dataset.add_record(record=DataRecordInput(**kwargs))
        await uow.commit()
