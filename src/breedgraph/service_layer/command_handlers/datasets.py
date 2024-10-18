from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.datasets import DataSetInput, DataRecordInput
from src.breedgraph.domain.model.ontology import ScaleType

from src.breedgraph.service_layer.parsers import ValueParser

import logging

logger = logging.getLogger(__name__)

async def add_dataset(
        cmd: commands.datasets.AddDataSet,
        uow: unit_of_work.AbstractUnitOfWork
):
    kwargs = cmd.model_dump()
    async with uow.get_repositories(user_id=kwargs.pop('user')) as uow:
        await uow.datasets.create(DataSetInput(**kwargs))
        await uow.commit()

async def add_record(
        cmd: commands.datasets.AddRecord,
        uow: unit_of_work.AbstractUnitOfWork
):
    kwargs = cmd.model_dump()
    async with uow.get_repositories(user_id=kwargs.pop('user')) as uow:
        dataset = await uow.datasets.get(dataset_id=kwargs.pop('dataset'))
        ontology = await uow.ontologies.get(entry_id = dataset.term)
        term = ontology.get_entry_model(dataset.term)
        scale = ontology.get_entry_model(ontology.get_scale_id(term.id))
        if scale.scale_type in [ScaleType.ORDINAL, ScaleType.NOMINAL]:
            category_ids = ontology.get_category_ids(scale.id)
            categories = [ontology.get_entry_model(c) for c in category_ids]
        else:
            categories = None
        if scale.scale_type == ScaleType.GERMPLASM:
            germplasms = [g async for g in uow.germplasms.get_all()]
        else:
            germplasms = None
        kwargs['value'] = ValueParser().parse(
            value=kwargs.get('value'),
            scale=scale,
            categories=categories,
            germplasms=germplasms
        )
        dataset.add_record(record=DataRecordInput(**kwargs))
        await uow.commit()
