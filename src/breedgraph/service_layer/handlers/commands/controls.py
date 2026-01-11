from src.breedgraph.domain import commands
from src.breedgraph.domain.model.controls import Control, Access


from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService


from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def set_release(
        cmd: commands.controls.SetRelease,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        control_service: AbstractAccessControlService = uow.controls
        admin_teams = control_service.access_teams.get(Access.ADMIN)
        await uow.controls.set_controls_by_id_and_label(
            user_id=cmd.agent_id,
            ids=cmd.entity_ids,
            label=cmd.entity_label,
            control_teams=admin_teams,
            release=cmd.release
        )
        await uow.commit()