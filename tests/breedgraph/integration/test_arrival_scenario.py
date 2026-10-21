"""
The arrivals builder (tests/breedgraph/scenarios/arrival_scenario.py): what it declares is what the views read back,
for the writer, who reads it all, and the hidden sample a placeholder for the outsider.
"""
import pytest

from tests.breedgraph.scenarios.arrival_scenario import UNITS, HIDDEN, LIGHT, HEIGHT, STORE, LAB_STORE

DECLARED = {**UNITS, **{name: unit for name, (_, unit) in HIDDEN.items()}}


def test_units(arrivals):
    assert set(arrivals.units) == set(DECLARED)


@pytest.mark.asyncio(loop_scope="session")
async def test_units_as_declared(views_factory, read_policy, arrivals):
    async with views_factory.get_views(user_id=read_policy['writer']) as views:
        units = await views.units.get_units(arrivals.units.values())
        store = (await views.location_trees.get_locations([arrivals.ids[STORE]]))[arrivals.ids[STORE]]
    assert (store.name, store.parent) == (LAB_STORE, read_policy['lab'])

    def location_id(key: str) -> int:
        return arrivals.ids[STORE] if key == STORE else read_policy[key]

    def as_text(time):
        return None if time is None else str(time)

    by_name = {unit.name: unit for unit in units.values()}
    for name, (subject_key, parents, germplasm_key, positions) in DECLARED.items():
        unit = by_name[name]
        assert unit.subject == read_policy[subject_key], name
        assert set(unit.parents) == {arrivals.units[parent] for parent in parents}, name
        assert unit.germplasm == (read_policy[germplasm_key] if germplasm_key else None), name
        assert [(p.location_id, as_text(p.start), as_text(p.end)) for p in unit.positions] == [
            (location_id(location), start, end) for location, start, end in positions
        ], name


@pytest.mark.asyncio(loop_scope="session")
async def test_the_hidden_sample_is_a_placeholder_for_the_outsider(views_factory, read_policy, arrivals):
    async with views_factory.get_views(user_id=read_policy['outsider']) as views:
        units = await views.units.get_units([arrivals.units['Arrival Sample Hidden'], arrivals.units['Arrival Extract Hidden']])
    assert units[arrivals.units['Arrival Sample Hidden']].name == 'REDACTED'
    assert units[arrivals.units['Arrival Extract Hidden']].name == 'Arrival Extract Hidden'


@pytest.mark.asyncio(loop_scope="session")
async def test_datasets(views_factory, read_policy, arrivals):
    names = {unit_id: name for name, unit_id in arrivals.units.items()}
    async with views_factory.get_views(user_id=read_policy['writer']) as views:
        for key, values in (('light', LIGHT), ('height', HEIGHT)):
            records = await views.datasets.get_records(arrivals.datasets[key])
            assert {names[record['unit']]: record['value'] for record in records} == values, key
