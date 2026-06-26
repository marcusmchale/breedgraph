from breedgraph.domain.commands.setup import LoadReadModel

from breedgraph.adapters.redis.state_store import RedisStateStore

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def load_read_model(
        _cmd: LoadReadModel,
        state_store: RedisStateStore
):
    pass
