
from abc import ABC, abstractmethod

from src.breedgraph.domain.model.blocks import Block
from src.breedgraph.custom_exceptions import IllegalOperationError

import logging
logger = logging.getLogger(__name__)

class AbstractExtraAggregateService(ABC):
    """
    Persistence service for germplasm operations.
    Handles data operations and validation queries for germplasm entries.
    """

    async def split_block(self, block: Block, unit_id: int) -> None:
        """Split an aggregate at the given unit ID"""
        logger.debug(f"Splitting block at unit: {unit_id}")

        if not block.can_split(unit_id):
            raise IllegalOperationError("Cannot split aggregate at this node as there are child nodes that would still be connected to other members of the aggregate")
        # Also ensure the unit has a position defined
        if not block.get_unit(unit_id).positions:
            raise IllegalOperationError("Cannot split aggregate at this node as the new root node does not have a position defined")

        for parent_id in block.get_parent_ids(unit_id):
            await self._delete_relationship(
                source_id = parent_id,
                source_label = block.get_unit(parent_id).label,
                sink_id = unit_id,
                sink_label = block.get_unit(unit_id).label,
                relationship_label = block.default_edge_label
            )

    @abstractmethod
    async def _delete_relationship(self, source_id, source_label, sink_id, sink_label, relationship_label):
        raise NotImplementedError





