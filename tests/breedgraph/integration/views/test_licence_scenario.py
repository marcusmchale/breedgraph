"""
The licence scenario of the test database (tests/breedgraph/scenarios/licence_scenario.py), on the read-policy
scenario: who must accept each licence, what its text was read as, and that the licences are released as widely as
their studies and datasets (docs/licences.md §1, §5)
"""
import pytest
import pytest_asyncio

from breedgraph.adapters.neo4j.cypher.query_builders.controls import licence_release_violations
from breedgraph.domain.model.references import TextFormat

from tests.breedgraph.scenarios.licence_scenario import LicenceScenarioBuilder, MARKDOWN_LICENCE


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
            study_ids=[licences.ids['public_study'], licences.ids['registered_study']], dataset_ids=[], reference_ids=[]
        )
        assert [record.data() async for record in result] == []
