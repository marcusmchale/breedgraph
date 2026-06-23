from asyncio import Queue

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory

from src.breedgraph.domain import commands, events
from src.breedgraph.domain.model.errors import ItemError
from src.breedgraph.domain.model.submissions import SubmissionStatus

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def submit_records(
        cmd: commands.datasets.SubmitRecords,
        event_queue: Queue
):
    event = events.datasets.RecordsSubmitted(agent_id=cmd.agent_id, submission_id=cmd.submission_id)
    await event_queue.put(event)

@handlers.command_handler()
async def update_records(
        cmd: commands.datasets.UpdateRecords,
        event_queue: Queue
):
    event = events.datasets.RecordUpdatesSubmitted(agent_id=cmd.agent_id, submission_id=cmd.submission_id)
    await event_queue.put(event)

@handlers.command_handler()
async def remove_records(
        cmd: commands.datasets.RemoveRecords,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=cmd.dataset_id)
        item_errors = []
        for i, e in enumerate(dataset.remove_records(cmd.record_ids)):
            if e is not None:
                item_errors.append(ItemError(index=i, error=e))
                continue

        if item_errors:
            raise ValueError(f"Failed to remove some records: {item_errors}")

        await uow.commit()

