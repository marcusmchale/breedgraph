from src.breedgraph.domain.commands.setup import LoadReadModel
from src.breedgraph.adapters.redis.read_model import ReadModel
import logging

logger = logging.getLogger(__name__)

async def load_read_model(
        _cmd: LoadReadModel,
        read_model: ReadModel
):
    pass
