"""
The licence gate (docs/licences.md §5): a dataset's records and dimensions, analyses of it and downloads of the files
its records cite need its study's licence accepted at its current text, through licencesAccept, unless the user reads
the dataset or its study through a controlling team. Acceptances are kept in the same cookie as the Terms of Use.
A file's download needs the licences of every dataset citing it, seen or not, unless the user owns the file; the
download state lists those still to accept.
"""
import uuid
from http.cookies import SimpleCookie

import pytest
import pytest_asyncio

from breedgraph.config import GQL_API_PATH
from breedgraph.domain.commands.programs import CreateStudy
from breedgraph.domain.commands.references import CreateLegalReference, UpdateLegalReference
from breedgraph.config import FILE_STORAGE_PATH
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.references import FileReferenceInput

from tests.breedgraph.e2e.utils import get_verified_payload, terms_cookie
from tests.breedgraph.e2e.analysis.test_analysis_api import descriptive_analysis
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.read_policy_scenario import store_file

DATASET = """
    query ($ids: [ID!]) { datasets(ids: $ids) { status result {
        id licenceRequired licence { id contentHash accepted } records { value } dimensions { recordCount }
    } errors { message } } }
"""
ACCEPT = "mutation ($licences: [LicenceAcceptanceInput!]!) { licencesAccept(licences: $licences) { status errors { message } } }"
DOWNLOAD = "query ($id: ID!) { referencesFileDownload(fileId: $id) { status errors { name message } } }"
STATE = "query ($id: ID!) { referencesFileDownloadState(fileId: $id) { status result { status licences { id contentHash } } errors { message } } }"
SUBMIT = "mutation ($analysis: AnalysisInput!) { analysisSubmit(analysis: $analysis) { status errors { name message path } } }"


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def licensed(dataset_build_context, uow_factory, bus):
    """A public study with a public licence, and a public dataset whose record cites a public data file"""
    context = dataset_build_context
    user_id, team_id = context['user_id'], context['team_id']
    licence_id = await bus.handle(CreateLegalReference(
        agent_id=user_id, write_team=team_id, release=ReadRelease.PUBLIC, description='Data licence', text='Use with credit.'
    ))
    name = f'Licensed study {uuid.uuid4().hex[:8]}'
    await bus.handle(CreateStudy(
        agent_id=user_id, write_team=team_id, release=ReadRelease.PUBLIC, trial_id=context['trial_id'], name=name,
        licence_id=licence_id
    ))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(trial_id=context['trial_id'])
        study_id = next(s.id for s in program.get_trial(context['trial_id']).studies.values() if s.name == name)
    file_id = uuid.uuid4().hex
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id, release=ReadRelease.PUBLIC) as uow:
        data_file = await uow.repositories.references.create(FileReferenceInput(
            description='Raw data', filename='raw.csv', content_type='text/csv', file_id=file_id
        ))
        dataset = await uow.repositories.datasets.create(DatasetInput(
            concept=context['concept_id'], study=study_id,
            records=[DataRecordInput(unit_id=context['unit_id'], value='12', reference_ids=[data_file.id])]
        ))
        await uow.commit()
    return {
        **context,
        'licence_id': licence_id,
        'dataset_id': dataset.id,
        'file_id': file_id,
        'outsider_id': await AccountBuilder(uow_factory=uow_factory).account()
    }


def cookies(client, login_token: str | None = None, **acceptances: str) -> dict:
    """Headers with the CSRF token, a session if given, and these acceptance cookies"""
    parts = [f"csrf_token={client.headers['X-CSRF-Token']}"]
    if login_token:
        parts.append(f"auth_token={login_token}")
    parts += [f"{name}={value}" for name, value in acceptances.items()]
    return {"X-CSRF-Token": client.headers['X-CSRF-Token'], "Cookie": "; ".join(parts)}


def accepting_terms(client, login_token: str | None, user_id: int | None) -> dict:
    """Headers of someone who has accepted the Terms of Use, and nothing more"""
    name, value = terms_cookie(user_id).split('=', 1)
    return cookies(client, login_token, **{name: value})


def set_cookie(response, name: str) -> str:
    for header in response.headers.get_list('set-cookie'):
        cookie = SimpleCookie(header)
        if name in cookie:
            return cookie[name].value
    raise AssertionError(f"{name} was not set")


async def post(client, headers: dict, query: str, variables: dict):
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables}, headers=headers)


async def read_dataset(client, headers: dict, dataset_id: int) -> tuple[dict, list]:
    body = (await post(client, headers, DATASET, {'ids': [dataset_id]})).json()
    return body['data']['datasets']['result'][0], [error['message'] for error in body.get('errors') or []]


async def accept(client, headers: dict, licence_id: int, content_hash: str):
    return await post(client, headers, ACCEPT, {'licences': [{'id': licence_id, 'contentHash': content_hash}]})


@pytest.mark.asyncio(loop_scope="session")
async def test_the_datas_owners_need_not_accept_its_licence(licensed, client, login_token_factory):
    headers = accepting_terms(client, login_token_factory(licensed['user_id']), licensed['user_id'])
    dataset, errors = await read_dataset(client, headers, licensed['dataset_id'])
    assert errors == []
    assert dataset['licenceRequired'] is False
    assert dataset['licence']['id'] == str(licensed['licence_id'])
    assert [record['value'] for record in dataset['records']] == ['12']
    assert dataset['dimensions']['recordCount'] == 1
    download = get_verified_payload(await post(client, headers, DOWNLOAD, {'id': licensed['file_id']}), "referencesFileDownload")
    assert download['status'] == 'SUCCESS'


@pytest.mark.asyncio(loop_scope="session")
async def test_others_get_the_data_once_they_accept_its_licence(licensed, client, login_token_factory):
    outsider = licensed['outsider_id']
    token = login_token_factory(outsider)
    headers = accepting_terms(client, token, outsider)

    dataset, errors = await read_dataset(client, headers, licensed['dataset_id'])
    assert dataset['licenceRequired'] is True and dataset['licence']['accepted'] is False
    assert dataset['records'] is None and dataset['dimensions'] is None
    assert len(errors) == 2 and all('licencesAccept' in error for error in errors)
    download = get_verified_payload(await post(client, headers, DOWNLOAD, {'id': licensed['file_id']}), "referencesFileDownload")
    assert (download['status'], download['errors'][0]['name']) == ('ERROR', 'LicenceNotAcceptedError')
    submitted = get_verified_payload(
        await post(client, headers, SUBMIT, {'analysis': descriptive_analysis(licensed['dataset_id'], licensed['concept_id'])}),
        "analysisSubmit"
    )
    assert [(error['name'], error['path']) for error in submitted['errors']] == [('LICENCE_NOT_ACCEPTED', ['datasetIds', '0'])]

    stale = get_verified_payload(await accept(client, headers, licensed['licence_id'], 'an earlier text'), "licencesAccept")
    assert stale['status'] == 'ERROR' and 'has changed' in stale['errors'][0]['message']

    response = await accept(client, headers, licensed['licence_id'], dataset['licence']['contentHash'])
    assert get_verified_payload(response, "licencesAccept")['status'] == 'SUCCESS'
    # the licence joins the Terms in the account's acceptance cookie
    accepted = cookies(client, token, **{f'acceptances_{outsider}': set_cookie(response, f'acceptances_{outsider}')})
    dataset, errors = await read_dataset(client, accepted, licensed['dataset_id'])
    assert errors == []
    assert dataset['licence']['accepted'] is True
    assert [record['value'] for record in dataset['records']] == ['12']
    download = get_verified_payload(await post(client, accepted, DOWNLOAD, {'id': licensed['file_id']}), "referencesFileDownload")
    assert download['status'] == 'SUCCESS'
    submitted = get_verified_payload(
        await post(client, accepted, SUBMIT, {'analysis': descriptive_analysis(licensed['dataset_id'], licensed['concept_id'])}),
        "analysisSubmit"
    )
    assert submitted['status'] == 'SUCCESS', submitted['errors']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_visitor_who_isnt_signed_in_accepts_too(licensed, client):
    headers = accepting_terms(client, None, None)
    dataset, errors = await read_dataset(client, headers, licensed['dataset_id'])
    assert dataset['licenceRequired'] is True and dataset['records'] is None and errors

    response = await accept(client, headers, licensed['licence_id'], dataset['licence']['contentHash'])
    assert get_verified_payload(response, "licencesAccept")['status'] == 'SUCCESS'
    accepted = cookies(client, None, acceptances=set_cookie(response, 'acceptances'))
    dataset, errors = await read_dataset(client, accepted, licensed['dataset_id'])
    assert errors == [] and [record['value'] for record in dataset['records']] == ['12']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_licence_the_user_cannot_read_cannot_be_accepted(licensed, client, login_token_factory, bus):
    hidden_id = await bus.handle(CreateLegalReference(
        agent_id=licensed['user_id'], write_team=licensed['team_id'], release=ReadRelease.PRIVATE, text='Private terms'
    ))
    outsider = licensed['outsider_id']
    headers = accepting_terms(client, login_token_factory(outsider), outsider)
    refused = get_verified_payload(await accept(client, headers, hidden_id, 'any'), "licencesAccept")
    assert refused['status'] == 'ERROR' and f'Licence {hidden_id} was not found' in refused['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_changed_licence_is_asked_for_again(licensed, client, login_token_factory, bus):
    outsider = licensed['outsider_id']
    token = login_token_factory(outsider)
    headers = accepting_terms(client, token, outsider)
    dataset, _ = await read_dataset(client, headers, licensed['dataset_id'])
    response = await accept(client, headers, licensed['licence_id'], dataset['licence']['contentHash'])
    accepted = cookies(client, token, **{f'acceptances_{outsider}': set_cookie(response, f'acceptances_{outsider}')})
    assert (await read_dataset(client, accepted, licensed['dataset_id']))[0]['records'] is not None

    await bus.handle(UpdateLegalReference(
        agent_id=licensed['user_id'], reference_id=licensed['licence_id'], text='Use with credit, and not for profit.'
    ))
    dataset, errors = await read_dataset(client, accepted, licensed['dataset_id'])
    assert dataset['licence']['accepted'] is False and dataset['records'] is None and errors


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def hidden_citer(dataset_build_context, uow_factory, bus):
    """
    A registered data file of another team's, cited only by a private dataset of a registered study with a registered
    licence: registered users read the file, and the licence, but not the dataset
    """
    context = dataset_build_context
    user_id, team_id = context['user_id'], context['team_id']
    owner = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    licence_id = await bus.handle(CreateLegalReference(
        agent_id=user_id, write_team=team_id, release=ReadRelease.REGISTERED, description='Data licence', text='Credit us.'
    ))
    name = f'Privately cited study {uuid.uuid4().hex[:8]}'
    await bus.handle(CreateStudy(
        agent_id=user_id, write_team=team_id, release=ReadRelease.REGISTERED, trial_id=context['trial_id'], name=name,
        licence_id=licence_id
    ))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(trial_id=context['trial_id'])
        study_id = next(s.id for s in program.get_trial(context['trial_id']).studies.values() if s.name == name)
    file_id = uuid.uuid4().hex
    async with uow_factory.get_uow(user_id=owner['user_id'], write_team=owner['team_id'], release=ReadRelease.REGISTERED) as uow:
        data_file = await uow.repositories.references.create(FileReferenceInput(
            description='Raw data', filename='raw.csv', content_type='text/csv', file_id=file_id
        ))
        await uow.commit()
    await store_file(FILE_STORAGE_PATH, bus.archival_service, file_id, b"unit,height\ntree,12\n")
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id, release=ReadRelease.PRIVATE) as uow:
        await uow.repositories.datasets.create(DatasetInput(
            concept=context['concept_id'], study=study_id,
            records=[DataRecordInput(unit_id=context['unit_id'], value='12', reference_ids=[data_file.id])]
        ))
        await uow.commit()
    return {
        'licence_id': licence_id,
        'file_id': file_id,
        'file_owner_id': owner['user_id'],
        'outsider_id': await AccountBuilder(uow_factory=uow_factory).account()
    }


async def download_state(client, headers: dict, file_id: str) -> dict:
    payload = get_verified_payload(await post(client, headers, STATE, {'id': file_id}), "referencesFileDownloadState")
    assert payload['status'] == 'SUCCESS', payload['errors']
    return payload['result']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_file_needs_the_licence_of_a_dataset_citing_it_the_user_cannot_see(hidden_citer, client, login_token_factory):
    outsider = hidden_citer['outsider_id']
    token = login_token_factory(outsider)
    headers = accepting_terms(client, token, outsider)

    state = await download_state(client, headers, hidden_citer['file_id'])
    assert [licence['id'] for licence in state['licences']] == [str(hidden_citer['licence_id'])]
    download = get_verified_payload(await post(client, headers, DOWNLOAD, {'id': hidden_citer['file_id']}), "referencesFileDownload")
    assert (download['status'], download['errors'][0]['name']) == ('ERROR', 'LicenceNotAcceptedError')

    # the licence is readable to whoever reads the file, so it can be accepted from the download, without the dataset
    response = await accept(client, headers, hidden_citer['licence_id'], state['licences'][0]['contentHash'])
    assert get_verified_payload(response, "licencesAccept")['status'] == 'SUCCESS'
    accepted = cookies(client, token, **{f'acceptances_{outsider}': set_cookie(response, f'acceptances_{outsider}')})
    assert (await download_state(client, accepted, hidden_citer['file_id']))['licences'] == []
    download = get_verified_payload(await post(client, accepted, DOWNLOAD, {'id': hidden_citer['file_id']}), "referencesFileDownload")
    assert download['status'] == 'SUCCESS', download['errors']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_files_owners_need_not_accept_the_licences_of_data_citing_it(hidden_citer, client, login_token_factory):
    owner = hidden_citer['file_owner_id']
    headers = accepting_terms(client, login_token_factory(owner), owner)
    assert (await download_state(client, headers, hidden_citer['file_id']))['licences'] == []
    download = get_verified_payload(await post(client, headers, DOWNLOAD, {'id': hidden_citer['file_id']}), "referencesFileDownload")
    assert download['status'] == 'SUCCESS', download['errors']
