from breedgraph.custom_exceptions import UnauthorisedOperationError, IllegalOperationError
from breedgraph.domain import commands
from breedgraph.domain.model.controls import Access
from breedgraph.domain.model.control_transfers import ControlledEntity

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

        if cmd.entity_ids is not None and cmd.entity_label is None:
            raise IllegalOperationError("Give the label of the entities with their ids")
        listed = None if cmd.entity_ids is None else [
            ControlledEntity(label=cmd.entity_label, id=entity_id) for entity_id in cmd.entity_ids
        ]
        entities = await control_service.entities_or_scope(listed, cmd.scope)
        if not entities:
            return
        await uow.controls.set_controls_by_id_and_label(
            ids=[entity.id for entity in entities],
            label=entities[0].label,
            control_teams=admin_teams,
            release=cmd.release
        )
        await uow.commit()