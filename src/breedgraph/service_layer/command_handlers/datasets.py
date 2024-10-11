from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.datasets import DataSetInput, DataRecordInput
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
        unit = kwargs.pop('unit')
        dataset.add_record(unit=unit, record=DataRecordInput(**kwargs))
        await uow.commit()
