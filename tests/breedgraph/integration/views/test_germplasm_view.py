"""
Germplasm under the read policy (docs/read-access.md), on the read-policy scenario (GERMPLASM in
tests/breedgraph/scenarios/read_policy_scenario.py): a public lineage with private, registered and other-team entries
in it, a hidden crop with a public child, and a public hybrid with the hidden crop as one parent.

A readable entry is linked to its nearest readable sources and sinks (or crops, for sources) through hidden entries
only: a direct link keeps its type, one through hidden entries is UNKNOWN (rule 3). A hidden crop is a placeholder
holding the readable entries below it (rule 4); other hidden entries are bare placeholders by id (rule 2) and are
left out of lists (rule 5).
"""
import pytest

from breedgraph.domain.model.germplasm import GermplasmSourceType

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, GERMPLASM, GermplasmEntryView

REDACTED = 'REDACTED'


def by_name(read_policy, relationships, end: str) -> dict[str, str]:
    """Relationships as {name of the other end: source type}"""
    names = {read_policy[name]: name for name in GERMPLASM}
    return {names[getattr(relationship, f'{end}_id')]: GermplasmSourceType(relationship.source_type).value
            for relationship in relationships}


def assert_entry(read_policy, viewer: str, name: str, entry):
    expected = read_policy.germplasm_entry(viewer, name)
    assert entry.id == read_policy[name]
    assert (entry.name != REDACTED) == expected.readable, f"{viewer}: {name}"
    if not expected.readable:
        assert entry.description is None
        assert entry.references == () or not entry.references
    assert by_name(read_policy, entry.sources, 'source') == expected.sources, f"{viewer}: sources of {name}"
    assert by_name(read_policy, entry.sinks, 'sink') == expected.sinks, f"{viewer}: sinks of {name}"
    # every relationship names this entry as its other end
    assert all(relationship.sink_id == entry.id for relationship in entry.sources)
    assert all(relationship.source_id == entry.id for relationship in entry.sinks)


def test_expected_shapes(read_policy):
    """The helper's expectations for a few entries, worked out by hand"""
    entry = read_policy.germplasm_entry
    # the outsider skips crop_middle and crop_other
    assert entry('outsider', 'crop_leaf') == GermplasmEntryView(
        True, {'crop': 'UNKNOWN'}, {'crop_line': 'SEED', 'crop_other_child': 'UNKNOWN', 'hybrid': 'MATERNAL'}
    )
    # anonymous also skips the registered crop_line, and sees nothing below crop_other
    assert entry('anonymous', 'crop_leaf').sinks == {'crop_line_public': 'UNKNOWN', 'hybrid': 'MATERNAL'}
    # the admin skips only the stranger's crop_other
    assert entry('admin', 'crop_leaf') == GermplasmEntryView(
        True, {'crop_middle': 'SEED'}, {'crop_line': 'SEED', 'crop_other_child': 'UNKNOWN', 'hybrid': 'MATERNAL'}
    )
    # a hidden crop is a source, and a placeholder holding its readable sinks
    assert entry('outsider', 'hybrid').sources == {'crop_leaf': 'MATERNAL', 'crop_private': 'PATERNAL'}
    assert entry('outsider', 'crop_private') == GermplasmEntryView(
        False, {}, {'crop_private_child': 'SEED', 'hybrid': 'PATERNAL'}
    )
    assert entry('outsider', 'crop_middle') == GermplasmEntryView(False, {}, {})
    assert read_policy.shown_crops('anonymous') == {'crop', 'crop_private'}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_entries_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        entries = {entry.id: entry for entry in await views.germplasm.get_entries(
            entry_ids=[read_policy[name] for name in GERMPLASM]
        )}
    assert set(entries) == {read_policy[name] for name in GERMPLASM}
    for name in GERMPLASM:
        assert_entry(read_policy, viewer, name, entries[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_all_entries_leave_hidden_out(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        entries = {entry.id: entry for entry in await views.germplasm.get_entries()}
    expected = [name for name in GERMPLASM if read_policy.readable(viewer, name)]
    assert set(entries) == {read_policy[name] for name in expected}
    for name in expected:
        assert_entry(read_policy, viewer, name, entries[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_crops(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        crops = {entry.id: entry for entry in await views.germplasm.get_crops()}
    expected = read_policy.shown_crops(viewer)
    assert set(crops) == {read_policy[name] for name in expected}
    for name in expected:
        assert_entry(read_policy, viewer, name, crops[read_policy[name]])
