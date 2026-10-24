"""
Arrivals (query_builders.unit_graphs, docs/read-access.md rule 5): each location's arrivals and their units as each
viewer sees them, as the arrivals scenario declares them (tests/breedgraph/scenarios/arrival_scenario.py), the units of
an arrival related to a unit, and its units by subject.
"""
import pytest
from numpy import datetime64

from breedgraph.domain.model.unit_graphs import arrival_key
from tests.breedgraph.scenarios.arrival_scenario import EXPECTED_ARRIVALS, STORE, LAB
from tests.breedgraph.scenarios.read_policy_scenario import LOCATION_PARENTS

VIEWERS = ('admin', 'writer', 'stranger', 'outsider', 'anonymous')


def _location(read_policy, arrivals, key: str) -> int:
    return arrivals.ids[STORE] if key == STORE else read_policy[key]


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_arrivals_as_each_viewer_sees_them(views_factory, read_policy, arrivals, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for key, by_viewer in EXPECTED_ARRIVALS.items():
            location_id = _location(read_policy, arrivals, key)
            seen = []
            for arrival in await views.units.get_arrivals([location_id]):
                assert arrival.location_id == location_id
                units = await views.units.get_arrival_units(location_id, arrival.start)
                assert arrival.unit_count == len(units), (key, arrival.start)
                seen.append((None if arrival.start is None else str(arrival.start), [unit.name for unit in units]))
            assert seen == by_viewer[viewer], (key, viewer)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('start', ('country', 'field', 'centre'))
async def test_arrivals_below_a_location(views_factory, read_policy, arrivals, viewer, start):
    """
    With below, the arrivals at a location and at every location under it, each at the location it came to, as each
    is listed alone; none when the search starts from a hidden location that is not a location tree's root
    """
    # the read-policy scenario's location trees, with the arrival scenario's store below its lab
    parents = {**LOCATION_PARENTS, STORE: LAB}
    under, pending = {start}, [start]
    while pending:
        current = pending.pop()
        children = [name for name, parent in parents.items() if parent == current]
        under.update(children)
        pending.extend(children)
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        below = await views.units.get_arrivals([_location(read_policy, arrivals, start)], below=True)
        each = [arrival for key in under for arrival in await views.units.get_arrivals([_location(read_policy, arrivals, key)])]
    searched = read_policy.readable(viewer, start) or parents[start] is None
    key = lambda arrival: (arrival.location_id, None if arrival.start is None else str(arrival.start), arrival.unit_count)
    assert sorted(map(key, below), key=str) == (sorted(map(key, each), key=str) if searched else []), (viewer, start)
    # newest first, undated last, as for one location
    dated = [arrival.start for arrival in below if arrival.start is not None]
    assert dated == sorted(dated, reverse=True) and all(a.start is not None for a in below[:len(dated)])


@pytest.mark.asyncio(loop_scope="session")
async def test_an_arrival_keeps_its_units_graph(views_factory, read_policy, arrivals):
    """Arrived units are read as any unit: with their parents and positions, and their unit graph's root given"""
    units = arrivals.units
    async with views_factory.get_views(user_id=read_policy['writer']) as views:
        (arrival,) = [a for a in await views.units.get_arrivals([read_policy[LAB]]) if str(a.start) == '2025-03-25']
        assert arrival.root_ids == [units['Arrival Field']]
        by_name = {unit.name: unit for unit in await views.units.get_arrival_units(read_policy[LAB], arrival.start)}
    assert set(by_name['Arrival Pooled'].parents) == {units['Arrival Tree A'], units['Arrival Tree B']}
    assert [(p.location_id, str(p.start)) for p in by_name['Arrival Sample A2'].positions] == [
        (read_policy[LAB], '2025-03-25'), (arrivals.ids[STORE], '2025-05-02')
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_arrivals_of_the_units_related_to_a_unit(views_factory, read_policy, arrivals):
    """Where the samples of a tree went, and the arrival that brought a unit's parent"""
    lab, units = read_policy[LAB], arrivals.units
    async with views_factory.get_views(user_id=read_policy['writer']) as views:
        below_tree = await views.units.get_arrivals([lab], unit_id=units['Arrival Tree A'])
        assert [None if a.start is None else str(a.start) for a in below_tree] == ['2025-03-25', '2024-11', None]
        recent = await views.units.get_arrival_units(lab, datetime64('2025-03-25'), unit_id=units['Arrival Tree A'])
        assert [u.name for u in recent] == [
            'Arrival Pooled', 'Arrival Sample A1', 'Arrival Sample A2', 'Arrival Sample A3', 'Arrival Sample Hidden'
        ]
        # a sample taken at the lab came with the arrival of the sample above it
        above = await views.units.get_arrival_units(lab, datetime64('2025-03-25'), unit_id=units['Arrival Extract A1'])
        assert [u.name for u in above] == ['Arrival Sample A1']


@pytest.mark.asyncio(loop_scope="session")
async def test_arrivals_are_matched_as_entered(views_factory, read_policy, arrivals):
    """A start is its precision: the arrival of 2024-11 is not one of 2024-11-01"""
    lab = read_policy[LAB]
    async with views_factory.get_views(user_id=read_policy['writer']) as views:
        assert [u.name for u in await views.units.get_arrival_units(lab, datetime64('2024-11'))] == ['Arrival Sample Own']
        assert await views.units.get_arrival_units(lab, datetime64('2024-11-01')) == []
        assert [u.name for u in await views.units.get_arrival_units(lab, None)] == ['Arrival Pooled Same']


@pytest.mark.asyncio(loop_scope="session")
async def test_arrival_units_by_subject_and_ids(views_factory, read_policy, arrivals):
    lab, units = read_policy[LAB], arrivals.units
    recent, moved = (lab, datetime64('2025-03-25')), (lab, datetime64('2025-06-10'))
    async with views_factory.get_views(user_id=read_policy['outsider']) as views:
        by_subject = await views.units.get_arrival_units_by_subject([recent, moved])
        ids = await views.units.get_arrival_unit_ids(*recent)
    sample = read_policy['ontology_subject_sample']
    assert [u.name for u in by_subject[arrival_key(*recent)][sample]] == [
        'Arrival Extract Hidden', 'Arrival Pooled', 'Arrival Sample A1', 'Arrival Sample A2', 'Arrival Sample A3',
        'Arrival Sample B1'
    ]
    assert [u.name for u in by_subject[arrival_key(*moved)][sample]] == ['Arrival Move Sample 1', 'Arrival Move Sample 2']
    assert sorted(ids) == sorted(u.id for u in by_subject[arrival_key(*recent)][sample])
    assert units['Arrival Sample Hidden'] not in ids
