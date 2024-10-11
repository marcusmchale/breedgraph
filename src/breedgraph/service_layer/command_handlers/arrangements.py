import logging

from src.breedgraph.domain import commands
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.arrangements import Arrangement, LayoutInput, LayoutStored

from src.breedgraph.custom_exceptions import IdentityExistsError

from src.breedgraph.service_layer import unit_of_work

logger = logging.getLogger(__name__)

async def add_layout(
        cmd: commands.arrangements.AddLayout,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user, release=ReadRelease[cmd.release]) as uow:
        if cmd.parent is None:
            layout_input = LayoutInput(**cmd.model_dump())
            await uow.arrangements.create(layout_input)
        else:
            arrangement = await uow.arrangements.get(layout_id=cmd.parent)
            arrangement.add_layout(LayoutInput(**cmd.model_dump()), parent_id=cmd.parent, position=cmd.position)
        await uow.commit()
