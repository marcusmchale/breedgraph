
from abc import ABC, abstractmethod

from breedgraph.domain.model.unit_graphs import UnitGraph

from breedgraph.custom_exceptions import IllegalOperationError

import logging
logger = logging.getLogger(__name__)

class AbstractAggregateRestructuringService(ABC):
    """
    Service for operations that span outside the aggregate boundaries.
    In theory, these operate under different bounded contexts,
     but as the operations are limited in scope we are handling them ad-hoc
     As these domain elements grow split them off into dedicated services
    """

    async def split_unit_graph(self, unit_graph: UnitGraph, unit_id: int) -> None:
        """Split an aggregate at the given unit ID"""
        logger.debug(f"Splitting unit graph at unit: {unit_id}")

        if not unit_graph.can_split(unit_id):
            raise IllegalOperationError("Cannot split aggregate at this node as there are child nodes that would still be connected to other members of the aggregate")
        # Also ensure the unit has a position defined
        if not unit_graph.get_unit(unit_id).positions:
            raise IllegalOperationError("Cannot split aggregate at this node as the new root node does not have a position defined")

        for parent_id in unit_graph.get_parent_ids(unit_id):
            await self._delete_relationship(
                source_id = parent_id,
                source_label = unit_graph.get_unit(parent_id).label,
                sink_id = unit_id,
                sink_label = unit_graph.get_unit(unit_id).label,
                relationship_label = unit_graph.default_edge_label
            )

    @abstractmethod
    async def _delete_relationship(self, source_id, source_label, sink_id, sink_label, relationship_label) -> None:
        ...


