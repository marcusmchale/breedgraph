import pytest

from tests.scenarios.reference_builder import ReferenceBuilder

@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get(
        uow_factory,
        reference_build_context
):
    user_id = reference_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        reference_input = ReferenceBuilder.legal_reference_input()
        reference = await uow.repositories.references.create(reference_input)
        await uow.commit()

    async with (uow_factory.get_uow(user_id=user_id) as uow):
        reference = await uow.repositories.references.get(reference_id=reference.id)
        assert reference
        assert reference.text == reference_input.text

@pytest.mark.asyncio(loop_scope="session")
async def test_edit(
        uow_factory,
        reference_build_context,
        lorem_text_generator
):
    user_id = reference_build_context['user_id']
    new_text = lorem_text_generator.new_text(10)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        reference_input = ReferenceBuilder.legal_reference_input()
        reference = await uow.repositories.references.create(reference_input)
        reference.text = new_text
        await uow.commit()

    async with (uow_factory.get_uow(user_id=user_id) as uow):
        reference = await uow.repositories.references.get(reference_id=reference.id)
        assert reference
        assert reference.text == new_text

@pytest.mark.asyncio(loop_scope="session")
async def test_file_reference(
        uow_factory,
        reference_build_context
):
    reference_input = ReferenceBuilder.file_reference_input()
    user_id = reference_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        reference = await uow.repositories.references.create(reference_input)
        await uow.commit()

    async with (uow_factory.get_uow(user_id=user_id) as uow):
        reference = await uow.repositories.references.get(reference_id=reference.id)
        assert reference
        assert reference.file_id == reference_input.file_id

