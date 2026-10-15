from breedgraph.domain.commands.setup import RefreshReadModels
from breedgraph.service_layer.infrastructure import AbstractReadModels

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def refresh_read_models(
        cmd: RefreshReadModels,
        read_models: AbstractReadModels
):
    await read_models.refresh(cmd.names)
