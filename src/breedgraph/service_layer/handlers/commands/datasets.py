from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from src.breedgraph.domain import commands
from src.breedgraph.domain.model.datasets import DataSetInput, DataSetStored, DataRecordInput
from src.breedgraph.domain.model.ontology import VariableStored, EventTypeStored, FactorStored, ScaleType

from src.breedgraph.domain.services.value_parsers import ValueParser

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_dataset(
        cmd: commands.datasets.CreateDataSet,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        await uow.repositories.datasets.create(DataSetInput(concept=cmd.concept_id))
        await uow.commit()

@handlers.command_handler()
async def add_record(
        cmd: commands.datasets.AddRecord,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        dataset: DataSetStored = await uow.repositories.datasets.get(dataset_id=cmd.dataset_id)
        ontology_service = uow.ontology
        scale_id = await ontology_service.get_scale_id(entry_id=dataset.concept)
        scale = await ontology_service.get_entry(scale_id)
        if scale.scale_type in [ScaleType.ORDINAL, ScaleType.NOMINAL]:
            category_ids = ontology_service.get_category_ids(scale.id)
            categories = [ontology_service.get_entry(c) for c in category_ids]
        else:
            categories = None
        value = ValueParser().parse(
            value=cmd.value,
            scale=scale,
            categories=categories,
            germplasm=uow.germplasm
        )
        record = DataRecordInput(
            unit=cmd.unit_id,
            value = value,
            start=cmd.start,
            end=cmd.end,
            references = cmd.references
        )
        dataset.add_record(record=record)
        await uow.commit()
