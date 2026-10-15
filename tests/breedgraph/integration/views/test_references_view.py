"""
References under the read policy (docs/read-access.md), on the read-policy scenario:

    reference_public (root, public, file), reference_private (child, private, file),
    reference_registered (root, registered, legal), reference_legal_private (child, private, legal)

A readable reference is returned in full. A hidden one asked for by id is a placeholder: its id, its type and a
REDACTED description, and never its file id or text (rule 2). Searches leave hidden references out (rule 5).
"""
import pytest

from breedgraph.domain.model.references import ReferenceType

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, REFERENCES

REDACTED = 'REDACTED'


def assert_reference(read_policy, viewer: str, name: str, reference):
    reference_type, description = REFERENCES[name]
    assert reference.id == read_policy[name]
    # the type is kept for placeholders too, as GraphQL needs it
    assert reference.type == ReferenceType(reference_type)
    if read_policy.readable(viewer, name):
        assert reference.description == description
        if reference_type == 'FILE':
            assert reference.file_id == read_policy.files[name][0]
            assert reference.filename == f"{name}.csv"
        else:
            assert reference.text
    else:
        assert reference.description == REDACTED
        if reference_type == 'FILE':
            assert reference.file_id is None
            assert reference.filename is None
        else:
            assert not reference.text or reference.text == REDACTED


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_references_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        references = {reference.id: reference for reference in await views.references.get_references(
            [read_policy[name] for name in REFERENCES]
        )}
    assert set(references) == {read_policy[name] for name in REFERENCES}
    for name in REFERENCES:
        assert_reference(read_policy, viewer, name, references[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_file_reference_by_file_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for name, (file_id, _) in read_policy.files.items():
            assert_reference(read_policy, viewer, name, await views.references.get_file_reference(file_id))
        assert await views.references.get_file_reference('not-a-stored-file') is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('reference_types', (None, [ReferenceType.LEGAL], [ReferenceType.FILE]))
async def test_search_leaves_hidden_out(views_factory, read_policy, viewer, reference_types):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        found = {reference.id: reference for reference in await views.references.search_references(
            'Readpolicy', reference_types
        )}
    expected = [
        name for name, (reference_type, _) in REFERENCES.items()
        if read_policy.readable(viewer, name)
        and (reference_types is None or ReferenceType(reference_type) in reference_types)
    ]
    assert set(found) == {read_policy[name] for name in expected}
    for name in expected:
        assert_reference(read_policy, viewer, name, found[read_policy[name]])
