import pytest

from breedgraph.domain.model.layout_trees import LayoutTree, LayoutInput
from breedgraph.domain.model.ontology import AxisType

@pytest.mark.asyncio(loop_scope="session")
async def test_create_row_layout_tree(
        uow_factory,
        layout_build_context
):
    user_id = layout_build_context['user_id']
    row_type_id = layout_build_context['ontology_layout_row']
    location_id = layout_build_context['location_id']
    async with uow_factory.get_uow(user_id=user_id, write_team=layout_build_context['team_id']) as uow:
        row_layout_input = LayoutInput(
            type=row_type_id,
            location=location_id,
            axes=[AxisType.ORDINAL]
        )
        layout_trees_repo = uow.repositories.layout_trees
        stored: LayoutTree = await layout_trees_repo.create(row_layout_input)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        layout_trees_repo = uow.repositories.layout_trees
        retrieved = await layout_trees_repo.get(layout_id = stored.root.id)
        assert stored.root == retrieved.root
        async for l in layout_trees_repo.get_all():
            if stored.root.id == l.root.id:
                break
        else:
            raise AssertionError("couldn't find stored layout tree by get all")

@pytest.mark.asyncio(loop_scope="session")
async def test_extend_row_with_grid(
        uow_factory,
        layout_build_context
):
    user_id = layout_build_context['user_id']
    row_type_id = layout_build_context['ontology_layout_row']
    grid_type_id = layout_build_context['ontology_layout_grid']
    location_id = layout_build_context['location_id']

    async with uow_factory.get_uow(user_id=user_id, write_team=layout_build_context['team_id']) as uow:
        row_layout_input = LayoutInput(
            type=row_type_id,
            location=location_id,
            axes=[AxisType.ORDINAL]
        )
        layout_trees_repo = uow.repositories.layout_trees
        layout_tree = await layout_trees_repo.create(row_layout_input)
        grid_layout_input_1 = LayoutInput(name = "layout 1", type=grid_type_id, location=layout_tree.root.location)
        grid_layout_input_2 = LayoutInput(name = "layout 2", type=grid_type_id)
        layout_tree.add_layout(layout=grid_layout_input_1, parent_id=layout_tree.root.id, position = ["1"])
        layout_tree.add_layout(layout=grid_layout_input_2, parent_id=layout_tree.root.id, position = ["2"])
        with pytest.raises(ValueError, match="Position should have same length as the parent layout axes"):
            layout_tree.add_layout(layout=grid_layout_input_2, parent_id=layout_tree.root.id, position=["3", "4"])
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        layout_trees_repo = uow.repositories.layout_trees
        layout_tree = await layout_trees_repo.get(layout_id = layout_tree.root.id)
        found = 0
        for k, v in layout_tree.get_sinks(layout_tree.root.id).items():
            if v.name in [grid_layout_input_1.name, grid_layout_input_2.name]:
                found += 1
        assert found == 2
