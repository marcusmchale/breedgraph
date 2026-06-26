from breedgraph.custom_exceptions import UnauthorisedOperationError
from breedgraph.domain import commands
from breedgraph.domain.model.controls import Control, Access


from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory
from breedgraph.service_layer.application.access_control import AbstractAccessControlService


from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def set_release(
        cmd: commands.controls.SetRelease,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        control_service: AbstractAccessControlService = uow.controls
        admin_teams = control_service.access_teams.get(Access.ADMIN)
        if not admin_teams:
            raise UnauthorisedOperationError("Admin affiliation required to set controls")
        await uow.controls.set_controls_by_id_and_label(
            ids=cmd.entity_ids,
            label=cmd.entity_label,
            control_teams=admin_teams,
            release=cmd.release
        )
        await uow.commit()