import pytest

from breedgraph.domain.model.arrangements import Arrangement, LayoutInput
from breedgraph.domain.model.ontology import AxisType

@pytest.mark.asyncio(loop_scope="session")
async def test_create_row_arrangement(
        uow_factory,
        layout_build_context
):
    user_id = layout_build_context['user_id']
    row_type_id = layout_build_context['ontology_layout_row']
    location_id = layout_build_context['location_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        row_layout_input = LayoutInput(
            type=row_type_id,
            location=location_id,
            axes=[AxisType.ORDINAL]
        )
        arrangements_repo = uow.repositories.arrangements
        stored: Arrangement = await arrangements_repo.create(row_layout_input)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        arrangements_repo = uow.repositories.arrangements
        retrieved = await arrangements_repo.get(layout_id = stored.root.id)
        assert stored.root == retrieved.root
        async for l in arrangements_repo.get_all():
            if stored.root.id == l.root.id:
                break
        else:
            raise AssertionError("couldn't find stored arrangement by get all")

@pytest.mark.asyncio(loop_scope="session")
async def test_extend_row_with_grid(
        uow_factory,
        layout_build_context
):
    user_id = layout_build_context['user_id']
    row_type_id = layout_build_context['ontology_layout_row']
    grid_type_id = layout_build_context['ontology_layout_grid']
    location_id = layout_build_context['location_id']

    async with uow_factory.get_uow(user_id=user_id) as uow:
        row_layout_input = LayoutInput(
            type=row_type_id,
            location=location_id,
            axes=[AxisType.ORDINAL]
        )
        arrangements_repo = uow.repositories.arrangements
        arrangement = await arrangements_repo.create(row_layout_input)
        grid_layout_input_1 = LayoutInput(name = "layout 1", type=grid_type_id, location=arrangement.root.location)
        grid_layout_input_2 = LayoutInput(name = "layout 2", type=grid_type_id)
        arrangement.add_layout(layout=grid_layout_input_1, parent_id=arrangement.root.id, position = ["1"])
        arrangement.add_layout(layout=grid_layout_input_2, parent_id=arrangement.root.id, position = ["2"])
        with pytest.raises(ValueError, match="Position should have same length as the parent layout axes"):
            arrangement.add_layout(layout=grid_layout_input_2, parent_id=arrangement.root.id, position=["3", "4"])
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        arrangements_repo = uow.repositories.arrangements
        arrangement = await arrangements_repo.get(layout_id = arrangement.root.id)
        found = 0
        for k, v in arrangement.get_sinks(arrangement.root.id).items():
            if v.name in [grid_layout_input_1.name, grid_layout_input_2.name]:
                found += 1
        assert found == 2
