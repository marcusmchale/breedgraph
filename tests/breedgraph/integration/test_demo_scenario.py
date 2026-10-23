"""
The demonstration database (tests/breedgraph/scenarios/demo/): what its story declares is what the views read back.
Who can read each entity is what DemoScenario.readable says, for each viewer: the story's accounts, an account in no
team and a visitor; Persons show as DemoScenario.person_view says; the 2026 plots are sown, in their blocks and
unrecorded; what the guide creates is not there yet; the licences are released widely enough; and the manifest
serialises, every key resolved.
"""
import json
from pathlib import Path

import pytest
import pytest_asyncio

from breedgraph.adapters.neo4j.cypher.query_builders.controls import licence_release_violations

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.demo import values
from tests.breedgraph.scenarios.demo.builder import VIEWERS
from tests.breedgraph.scenarios.demo.layout import plots, selection_plant_name
from tests.breedgraph.scenarios.demo.manifest import demo_manifest
from tests.breedgraph.scenarios.demo.story import (
    ACCOUNTS, DATASETS, GERMPLASM, GUIDE, HILL_FIELD, NEW_CROSS, PEOPLE, PLANS, STUDIES, TYPO
)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def viewers(demo, uow_factory) -> dict:
    """The user id of each viewer: None for a visitor, and an account in no team for 'registered'"""
    ids = {viewer: demo[viewer] for viewer in VIEWERS if viewer in ACCOUNTS}
    ids['registered'] = await AccountBuilder(uow_factory).account()
    ids['anonymous'] = None
    return ids


@pytest.mark.asyncio(loop_scope="session")
async def test_who_reads_what(demo, viewers, views_factory):
    """A viewer reads an entity when its controller shows them its writes, as it does only to those who can read it"""
    labels = set(demo.labels.values())
    for viewer, user_id in viewers.items():
        async with views_factory.get_views(user_id=user_id) as views:
            for label in labels:
                keys = [key for key, key_label in demo.labels.items() if key_label == label]
                controllers = await views.controls.get_controllers(label, [demo[key] for key in keys])
                wrong = [
                    key for key in keys
                    if bool(controllers[demo[key]].writes) != demo.readable(viewer, key)
                ]
                assert not wrong, f"{viewer} reads {label.value} {wrong} other than the story says"


@pytest.mark.asyncio(loop_scope="session")
async def test_person_views(demo, viewers, views_factory):
    for viewer, user_id in viewers.items():
        if user_id is None:
            continue  # visitors meet no Persons
        async with views_factory.get_views(user_id=user_id) as views:
            people = {person.id: person for person in await views.people.get_people([demo[key] for key in PEOPLE])}
        for key, person in PEOPLE.items():
            seen = people[demo[key]]
            assert seen.erased == person.erased, (viewer, key)
            if not person.erased:
                assert seen.view.name == demo.person_view(viewer, key), (viewer, key)


@pytest.mark.asyncio(loop_scope="session")
async def test_the_2026_plots_are_sown_in_their_blocks_and_unrecorded(demo, views_factory):
    plan = PLANS['lm26']
    laid_out = plots('lm26')
    async with views_factory.get_views(user_id=demo['theo']) as views:
        units = await views.units.get_units([demo.units[plot.name] for plot in laid_out])
        records = [
            record for dataset in DATASETS for record in await views.datasets.get_records(demo[dataset])
        ]
    for plot in laid_out:
        unit = units[demo.units[plot.name]]
        assert unit.germplasm == demo[plot.entry], plot.name
        [position] = unit.positions
        assert (position.location_id, position.layout_id) == (
            demo[plan.field], demo.layouts[f"lm26_block_{plot.block}"]
        ), plot.name
        assert [int(coordinate) for coordinate in position.coordinates] == [plot.row, plot.column], plot.name
        assert str(position.start) == plan.sown and position.end is None, plot.name
        if GERMPLASM[plot.entry].selected_from:
            assert [source.unit_id for source in unit.derived_from] == [demo.units[selection_plant_name()]]
    recorded = {record['unit'] for record in records}
    assert not recorded & {demo.units[plot.name] for plot in laid_out}


@pytest.mark.asyncio(loop_scope="session")
async def test_the_records_are_as_planned(demo, views_factory):
    async with views_factory.get_views(user_id=demo['dara']) as views:
        for key in ('height_2025', 'septoria_2025', 'heading_2025', 'nitrogen_2025'):
            records = await views.datasets.get_records(demo[key])
            expected = dict(values.plot_values('nf25', DATASETS[key].concept))
            names = {unit_id: name for name, unit_id in demo.units.items()}
            assert {names[record['unit']]: record['value'] for record in records} == expected, key
        weights = await views.datasets.get_records(demo['grain_weight_2025'])
    assert len(weights) == 2 * len(plots('nf25'))


@pytest.mark.asyncio(loop_scope="session")
async def test_what_the_guide_creates_is_not_there_yet(demo, uow_factory):
    async with uow_factory.get_uow() as uow:
        for label, name in (
                ('Trial', GUIDE['trial_2026']['name']),
                ('Study', GUIDE['study_2026']['name']),
                ('Location', HILL_FIELD.name),
                ('Germplasm', NEW_CROSS[0]),
                ('Person', GUIDE['new_person']['name']),
                ('User', GUIDE['invitee']['username']),
        ):
            result = await uow.tx.run(f"MATCH (n:{label}) WHERE n.name = $name RETURN count(n) AS found", name=name)
            assert (await result.single())['found'] == 0, (label, name)


@pytest.mark.asyncio(loop_scope="session")
async def test_licences_are_released_widely_enough(demo, uow_factory):
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(
            licence_release_violations(), study_ids=[demo[key] for key in STUDIES], dataset_ids=[], reference_ids=[]
        )
        assert [record async for record in result] == []


def test_the_manifest_serialises(demo):
    passwords = {key: 'demo-test-password' for key in ACCOUNTS}
    manifest = demo_manifest(demo, passwords, Path('files'), Path('uploads'), 'now', None)
    json.dumps(manifest)
    assert manifest['kind'] == 'demo'
    assert set(manifest['accounts']) == {key for key, account in ACCOUNTS.items() if not account.deleted}
    assert all(entity['id'] == demo[key] for key, entity in manifest['entities'].items())
    season = manifest['chains']['this_season']
    assert len(season['plots']) == len(plots('lm26'))
    plot_name, concept = TYPO
    assert season['typo']['typed'] == values.typed(season['typo']['correct'])
    assert dict(season['observations'][concept]['values'])[plot_name] == season['typo']['typed']
