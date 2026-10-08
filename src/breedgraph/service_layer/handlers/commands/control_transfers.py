from breedgraph.domain import commands
from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


@handlers.command_handler()
async def offer_control_transfer(
        cmd: commands.control_transfers.OfferControlTransfer,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        await uow.controls.offer_transfer(
            entities=cmd.entities,
            from_teams=cmd.from_teams,
            recipient_team=cmd.recipient_team,
            keep_from_teams=cmd.keep_from_teams,
            to_teams=cmd.to_teams,
            release=cmd.release
        )
        await uow.commit()

@handlers.command_handler()
async def accept_control_transfer(
        cmd: commands.control_transfers.AcceptControlTransfer,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        await uow.controls.accept_transfer(transfer_id=cmd.transfer_id, to_teams=cmd.to_teams, release=cmd.release)
        await uow.commit()

@handlers.command_handler()
async def reject_control_transfer(
        cmd: commands.control_transfers.RejectControlTransfer,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        await uow.controls.reject_transfer(transfer_id=cmd.transfer_id)
        await uow.commit()

@handlers.command_handler()
async def cancel_control_transfer(
        cmd: commands.control_transfers.CancelControlTransfer,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        await uow.controls.cancel_transfer(transfer_id=cmd.transfer_id)
        await uow.commit()

@handlers.command_handler()
async def renounce_control(
        cmd: commands.control_transfers.RenounceControl,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        await uow.controls.renounce_controls(entities=cmd.entities, team_ids=cmd.team_ids)
        await uow.commit()
