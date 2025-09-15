from src.breedgraph.domain.commands.setup import LoadReadModel

from src.breedgraph.adapters.redis.read_model import ReadModel

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def load_read_model(
        _cmd: LoadReadModel,
        read_model: ReadModel
):
    pass
