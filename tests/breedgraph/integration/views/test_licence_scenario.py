"""
The licence scenario of the test database (tests/breedgraph/scenarios/licence_scenario.py), on the read-policy
scenario: who must accept each licence, what its text was read as, that the licences are released as widely as
their studies, datasets and the files they cite (docs/licences.md §1, §5), and that a file cited only by a dataset the
reader can't see still needs its licence
"""
import pytest
import pytest_asyncio

from breedgraph.adapters.neo4j.cypher.query_builders.controls import licence_release_violations
from breedgraph.domain.model.references import TextFormat

from tests.breedgraph.scenarios.licence_scenario import LicenceScenarioBuilder, MARKDOWN_LICENCE, PRIVATELY_CITED_FILE


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def licences(read_policy, uow_factory):
    return await LicenceScenarioBuilder(uow_factory, read_policy).build()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer, required', [
    ('admin', False), ('writer', False), ('stranger', True), ('outsider', True), ('anonymous', True)
])
async def test_who_must_accept_the_public_studys_licence(read_policy, licences, views_factory, viewer, required):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        (dataset,) = await views.datasets.get_datasets(dataset_ids=[licences.ids['public_dataset']])
        file_licences = await views.datasets.get_file_licences(licences.files['Readpolicy licensed data'][0])
    assert dataset.licence == licences.ids['public_licence']
    assert dataset.licence_required is required
    assert [(f.dataset_id, f.licence_id, f.exempt) for f in file_licences] == [
        (licences.ids['public_dataset'], licences.ids['public_licence'], not required)
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_anonymous_visitors_see_nothing_of_the_registered_study(read_policy, licences, views_factory):
    async with views_factory.get_views(user_id=None) as views:
        (dataset,) = await views.datasets.get_datasets(dataset_ids=[licences.ids['registered_dataset']])
    assert dataset.redacted and dataset.licence is None and not dataset.licence_required


@pytest.mark.asyncio(loop_scope="session")
async def test_the_licences_are_read_from_their_files(read_policy, licences, views_factory):
    async with views_factory.get_views(user_id=read_policy.user('outsider')) as views:
        markdown, pdf = await views.references.get_references([licences.ids['public_licence'], licences.ids['registered_licence']])
    assert (markdown.text_format, markdown.filename, markdown.text) == (TextFormat.MARKDOWN, 'licence.md', MARKDOWN_LICENCE.decode().strip())
    assert (pdf.text_format, pdf.filename, pdf.content_type) == (TextFormat.PLAIN, 'licence.pdf', 'application/pdf')
    assert 'Use the data for research, with credit.' in pdf.text


@pytest.mark.asyncio(loop_scope="session")
async def test_the_licences_are_released_as_widely_as_their_data(licences, uow_factory):
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(
            licence_release_violations(),
            study_ids=[licences.ids['public_study'], licences.ids['registered_study']], dataset_ids=[],
            reference_ids=[licences.ids['data_file'], licences.ids['privately_cited_file']]
        )
        assert [record.data() async for record in result] == []


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer, needed', [('admin', False), ('writer', False), ('stranger', True), ('outsider', True)])
async def test_the_privately_cited_file_needs_its_licence_from_those_who_cant_see_its_dataset(
        read_policy, licences, views_factory, viewer, needed
):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        (dataset,) = await views.datasets.get_datasets(dataset_ids=[licences.ids['privately_cited_dataset']])
        file_licences = await views.datasets.get_file_licences(licences.files[PRIVATELY_CITED_FILE][0])
    # the child team's readers own the file and the dataset; others see neither the dataset nor its records
    assert dataset.redacted is needed
    assert [(f.dataset_id, f.licence_id) for f in file_licences] == [
        (licences.ids['privately_cited_dataset'], licences.ids['registered_licence'])
    ]
    assert any(f.exempt or f.file_owner for f in file_licences) is not needed
