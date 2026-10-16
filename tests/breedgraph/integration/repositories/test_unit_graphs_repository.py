import pytest

from breedgraph.domain.model import UnitInput

@pytest.mark.asyncio(loop_scope="session")
async def test_create(
        uow_factory,
        unit_graph_build_context
):
    user_id = unit_graph_build_context['user_id']
    tree_subject = unit_graph_build_context['ontology_subject_tree']
    tree_name = "Tree 1"
    async with uow_factory.get_uow(user_id=user_id, write_team=unit_graph_build_context['team_id']) as uow:
        stored_unit_graph = await uow.repositories.unit_graphs.create(UnitInput(
            name=tree_name,
            subject=tree_subject
        ))
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        retrieved = await uow.repositories.unit_graphs.get(unit_id=stored_unit_graph.root.id)
        assert retrieved.root.name == tree_name
        assert retrieved.root.subject == tree_subject


@pytest.mark.asyncio(loop_scope="session")
async def test_rename(
        uow_factory,
        unit_graph_build_context
):
    user_id = unit_graph_build_context['user_id']
    tree_subject = unit_graph_build_context['ontology_subject_tree']
    tree_name_1 = "Tree 1"
    tree_name_2 = "Tree One"
    async with uow_factory.get_uow(user_id=user_id, write_team=unit_graph_build_context['team_id']) as uow:
        stored_unit_graph = await uow.repositories.unit_graphs.create(UnitInput(
            name=tree_name_1,
            subject=tree_subject
        ))
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        retrieved = await uow.repositories.unit_graphs.get(unit_id=stored_unit_graph.root.id)
        retrieved.root.name = tree_name_2
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        retrieved = await uow.repositories.unit_graphs.get(unit_id=stored_unit_graph.root.id)
        assert retrieved.root.name == tree_name_2

