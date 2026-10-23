"""A layout tree's location is its root's, and the positions in it are at it (README, Layout)"""
import pytest

from breedgraph.custom_exceptions import IllegalOperationError, ProtectedNodeError
from breedgraph.domain.commands.layout_trees import UpdateLayout, DeleteLayout
from breedgraph.domain.commands.unit_graphs import CreateUnit


@pytest.mark.asyncio(loop_scope="session")
async def test_a_layout_tree_keeps_its_location_once_units_are_positioned_in_it(bus, uow_factory, unit_graph_build_context):
    context = unit_graph_build_context
    user_id, shelf_id = context['user_id'], context['layout_id']
    field_id, lab_id = context['location_field_id'], context['location_lab_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        layout_tree = await uow.repositories.layout_trees.get(layout_id=shelf_id)
        root, shelf = layout_tree.root, layout_tree.get_layout(shelf_id)

    def update(layout, location_id):
        return UpdateLayout(
            agent_id=user_id, layout_id=layout.id, location_id=location_id, type_id=layout.type, name=None,
            axes=list(layout.axes), parent=None
        )

    # only the root has a location, which can be corrected while no unit is positioned in the tree
    with pytest.raises(ValueError, match="Only the root of a layout tree has a location"):
        await bus.handle(update(shelf, lab_id))
    await bus.handle(update(root, lab_id))
    await bus.handle(update(root, field_id))

    await bus.handle(CreateUnit(
        agent_id=user_id, write_team=context['team_id'], location_id=field_id, layout_id=shelf_id, coordinates=["1", "1"]
    ))
    with pytest.raises(IllegalOperationError, match="Units are positioned in this layout tree"):
        await bus.handle(update(root, lab_id))
    with pytest.raises(ProtectedNodeError, match="Units are positioned in this layout"):
        await bus.handle(DeleteLayout(agent_id=user_id, layout_id=shelf_id))
    with pytest.raises(ProtectedNodeError, match="Units are positioned in this layout"):
        await bus.handle(DeleteLayout(agent_id=user_id, layout_id=root.id))
