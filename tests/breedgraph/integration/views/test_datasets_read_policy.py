"""
Datasets under the read policy (docs/read-access.md, section 3), on the read-policy scenario:

    dataset_public (child, public; study_public): records for tree_public, leaf_private, rhizosphere_public,
        tree_registered; contributions person_public, person_private; references reference_public
    dataset_private (child, private; study_public): a record for tree_public
    dataset_registered (root, registered; study_registered): a record for tree_public citing reference_private

A readable dataset is returned in full, records and all, its units and references kept as ids whether or not the
viewer can read them (rule 2). A hidden dataset is a placeholder asked for by id alone, and left out of searches.
The record-level reads (records, counts, unit ids, the unit tree, units by subject, dimensions) are given readable
datasets here: the resolvers filter the ids first (see the e2e tests).
"""
import pytest

from breedgraph.service_layer.queries.read_models.datasets import DatasetRead

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, DATASETS, UNIT_PARENTS

REDACTED = 'REDACTED'

UNIT_SUBJECTS = {
    'tree_public': 'ontology_subject_tree', 'tree_registered': 'ontology_subject_tree',
    'leaf_private': 'ontology_subject_leaf', 'rhizosphere_public': 'ontology_subject_rhizosphere',
}
UNIT_LOCATIONS = {'tree_public': 'state'}


def ids(read_policy, names) -> set[int]:
    return {read_policy[name] for name in names}


def readable_datasets(read_policy, viewer: str, names=DATASETS) -> list[str]:
    return [name for name in names if read_policy.readable(viewer, name)]


def below(unit: str) -> set[str]:
    found, pending = set(), [unit]
    while pending:
        current = pending.pop()
        children = [member for member, parent in UNIT_PARENTS.items() if parent == current]
        found.update(children)
        pending.extend(children)
    return found


def selected(read_policy, viewer: str, units: list[str]) -> set[str]:
    """The units a unitIds selection covers: each unit, and everything below the readable ones"""
    found = set()
    for unit in units:
        found |= {unit} | below(unit) if read_policy.readable(viewer, unit) else {unit}
    return found


def assert_header(read_policy, viewer: str, name: str, dataset: DatasetRead):
    assert dataset.id == read_policy[name]
    if read_policy.readable(viewer, name):
        expected = DATASETS[name]
        assert not dataset.redacted
        assert dataset.study == read_policy[expected['study']]
        assert dataset.concept == read_policy['ontology_variable_height']
        # links to people and references are kept as ids, readable or not (rule 2), except that anonymous users get
        # no contributors, as they see no Persons (docs/person.md §3)
        assert {contribution.person for contribution in dataset.contributions} == (
            set() if viewer == 'anonymous' else ids(read_policy, [person for person, _ in expected['contributions']])
        )
        assert all(isinstance(contribution.roles, list) for contribution in dataset.contributions)
        assert set(dataset.references) == ids(read_policy, expected['references'])
        assert dataset.record_count == len(expected['records'])
    else:
        assert dataset.redacted
        assert dataset.study is None
        assert dataset.contributions == []
        assert dataset.references == []
        assert dataset.record_count == 0


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_datasets_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        datasets = {dataset.id: dataset for dataset in await views.datasets.get_datasets(
            dataset_ids=[read_policy[name] for name in DATASETS]
        )}
    assert set(datasets) == ids(read_policy, DATASETS)
    for name in DATASETS:
        assert_header(read_policy, viewer, name, datasets[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_dataset_searches_leave_hidden_out(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for selection, names in (
                ({}, list(DATASETS)),
                ({'study_ids': [read_policy['study_public']]}, ['dataset_public', 'dataset_private']),
                ({'study_ids': [read_policy['study_registered']]}, ['dataset_registered']),
                ({'concept_ids': [read_policy['ontology_variable_height']]}, list(DATASETS)),
                # ids with a filter is a search too
                ({
                    'dataset_ids': [read_policy[name] for name in DATASETS],
                    'study_ids': [read_policy['study_public']]
                }, ['dataset_public', 'dataset_private']),
        ):
            datasets = {dataset.id: dataset for dataset in await views.datasets.get_datasets(**selection)}
            expected = readable_datasets(read_policy, viewer, names)
            assert set(datasets) == ids(read_policy, expected), f"{viewer}: {selection}"
            for name in expected:
                assert_header(read_policy, viewer, name, datasets[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('study', ('study_public', 'study_registered'))
async def test_dataset_summaries(views_factory, read_policy, viewer, study):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        summaries = {summary.id: summary for summary in await views.datasets.get_dataset_summaries(read_policy[study])}
    expected = readable_datasets(read_policy, viewer, [name for name in DATASETS if DATASETS[name]['study'] == study])
    assert set(summaries) == ids(read_policy, expected)
    for name in expected:
        summary = summaries[read_policy[name]]
        units = {unit for unit, _, _ in DATASETS[name]['records']}
        shown = {unit for unit in units if read_policy.readable(viewer, unit)}
        assert summary.concept_id == read_policy['ontology_variable_height']
        assert summary.record_count == len(DATASETS[name]['records'])
        # hidden units count, as their records are readable, but add no subjects, unit graphs or locations
        assert summary.unit_count == len(units)
        assert set(summary.subject_ids) == {read_policy[UNIT_SUBJECTS[unit]] for unit in shown}
        assert set(summary.unit_root_ids) == ({read_policy['field_unit']} if shown else set())
        assert set(summary.location_ids) == {read_policy[UNIT_LOCATIONS[unit]] for unit in shown if unit in UNIT_LOCATIONS}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('selection', (None, ['tree_public'], ['leaf_private'], ['field_unit'], ['tree_registered']))
async def test_records(views_factory, read_policy, viewer, selection):
    """A readable dataset's records, hidden units included as ids; unitIds expand only below readable units"""
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for name in readable_datasets(read_policy, viewer):
            unit_ids = [read_policy[unit] for unit in selection] if selection is not None else None
            covered = selected(read_policy, viewer, selection) if selection is not None else None
            expected = [
                (read_policy[unit], value, ids(read_policy, references))
                for unit, value, references in DATASETS[name]['records']
                if covered is None or unit in covered
            ]
            records = await views.datasets.get_records(dataset_id=read_policy[name], unit_ids=unit_ids)
            assert sorted((record['unit'], record['value'], frozenset(record['references'])) for record in records) == \
                sorted((unit, value, frozenset(references)) for unit, value, references in expected), f"{viewer}: {name}"
            assert await views.datasets.count_records(dataset_id=read_policy[name], unit_ids=unit_ids) == len(expected)
            assert await views.datasets.get_unit_ids(dataset_id=read_policy[name], unit_ids=unit_ids) == \
                sorted({unit for unit, _, _ in expected})


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_unit_tree(views_factory, read_policy, viewer):
    """Walk the whole tree of recorded units, level by level, against the policy's expectation"""
    datasets = readable_datasets(read_policy, viewer)
    names = {read_policy[unit]: unit for unit in UNIT_PARENTS}
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        pending = [None]
        while pending:
            parent = pending.pop()
            level = await views.datasets.get_unit_level(
                dataset_ids=[read_policy[name] for name in datasets],
                parent_ids=[read_policy[parent]] if parent else None
            )
            expected = read_policy.recorded_unit_level(viewer, datasets, parent)
            assert {names[node.id]: (node.unit_count, node.record_count, node.has_children) for node in level} == \
                expected, f"{viewer}: below {parent}"
            # readable units first, then placeholders
            readable_flags = [read_policy.readable(viewer, names[node.id]) for node in level]
            assert readable_flags == sorted(readable_flags, reverse=True)
            pending.extend(names[node.id] for node in level if node.has_children)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('selection', (None, ['tree_public'], ['leaf_private']))
async def test_units_by_subject(views_factory, read_policy, viewer, selection):
    datasets = readable_datasets(read_policy, viewer)
    recorded = {unit for name in datasets for unit, _, _ in DATASETS[name]['records']}
    if selection is not None:
        recorded &= selected(read_policy, viewer, selection)
    expected: dict[int | None, set[int]] = {}
    for unit in recorded:
        subject = read_policy[UNIT_SUBJECTS[unit]] if read_policy.readable(viewer, unit) else None
        expected.setdefault(subject, set()).add(read_policy[unit])

    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        by_subject = await views.datasets.get_units_by_subject(
            dataset_ids=[read_policy[name] for name in datasets],
            unit_ids=[read_policy[unit] for unit in selection] if selection is not None else None
        )
    assert {subject: {unit.id for unit in units} for subject, units in by_subject.items()} == expected
    for subject, units in by_subject.items():
        assert all((unit.name == REDACTED) == (subject is None) for unit in units)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_dimensions(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for name in readable_datasets(read_policy, viewer):
            dimensions = await views.datasets.get_dimensions(read_policy[name])
            records = DATASETS[name]['records']
            assert dimensions.record_count == len(records)
            assert dimensions.unit_count == len({unit for unit, _, _ in records})
