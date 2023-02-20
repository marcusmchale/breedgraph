from src.dbtools.domain.commands.setup import LoadReadModel, EnsureGlobalAdmin
from src.dbtools.adapters.redis.read_model import ReadModel
from src.dbtools.service_layer import unit_of_work


async def load_read_model(
        _cmd: LoadReadModel,
        read_model: ReadModel
):
    pass

