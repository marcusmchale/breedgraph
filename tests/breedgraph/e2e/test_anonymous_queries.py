"""
Which queries answer anonymous requests (docs/read-access.md, section 4), as a table over every Query field of the
schema, on the read-policy scenario.

OPEN queries answer without an account, showing what is released to the public; ACCOUNT queries refuse with the
authentication error. Every Query field must be in one table or the other, so a new query is classified when it is
added. What the open queries show anonymously is tested per domain (the *_read_api.py tests).
"""
from collections import defaultdict

import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload

AUTHENTICATION_ERROR = ('UnauthorisedOperationError', 'Please provide a valid token')


def open_queries(ids: dict, files: dict) -> dict[str, tuple[str, dict, bool]]:
    """{field: (query, variables, succeeds)}: open queries with arguments from the scenario"""
    public_file = files['reference_public'][0]
    return {
        'accountsInvitation': ('query { accountsInvitation(token: "not-a-token") { status errors { name message } } }', {}, False),
        'layoutsRoots': ('query ($id: ID!) { layoutsRoots(locationId: $id) { status errors { name message } } }', {'id': ids['field']}, True),
        'layoutsLayouts': ('query ($ids: [ID!]) { layoutsLayouts(ids: $ids) { status errors { name message } } }', {'ids': [ids['facility']]}, True),
        'unitsRoots': ('query ($ids: [ID!]) { unitsRoots(locationIds: $ids) { status errors { name message } } }', {'ids': [ids['field']]}, True),
        'unitsDescendantsBySubject': ('query ($ids: [ID!]!) { unitsDescendantsBySubject(unitIds: $ids) { status errors { name message } } }', {'ids': [ids['tree_public']]}, True),
        'unitsUnits': ('query ($ids: [ID!]) { unitsUnits(ids: $ids) { status errors { name message } } }', {'ids': [ids['tree_public']]}, True),
        'datasets': ('query ($ids: [ID!]) { datasets(ids: $ids) { status errors { name message } } }', {'ids': [ids['dataset_public']]}, True),
        'datasetsSummaries': ('query ($id: ID!) { datasetsSummaries(studyId: $id) { status errors { name message } } }', {'id': ids['study_public']}, True),
        'datasetsUnits': ('query ($ids: [ID!]!) { datasetsUnits(datasetIds: $ids) { status errors { name message } } }', {'ids': [ids['dataset_public']]}, True),
        'datasetsUnitsBySubject': ('query ($ids: [ID!]!) { datasetsUnitsBySubject(datasetIds: $ids) { status errors { name message } } }', {'ids': [ids['dataset_public']]}, True),
        'germplasmCrops': ('query { germplasmCrops { status errors { name message } } }', {}, True),
        'germplasmEntries': ('query ($ids: [ID!]) { germplasmEntries(ids: $ids) { status errors { name message } } }', {'ids': [ids['crop']]}, True),
        'ontology': ('query { ontology { status errors { name message } } }', {}, True),
        'ontologyEntries': ('query { ontologyEntries(labels: [SUBJECT]) { status errors { name message } } }', {}, True),
        'ontologyRelationships': ('query ($ids: [ID!]!) { ontologyRelationships(entryIds: $ids) { status errors { name message } } }', {'ids': [ids['ontology_subject_tree']]}, True),
        'ontologyVersion': ('query { ontologyVersion { status errors { name message } } }', {}, True),
        'programs': ('query { programs { status errors { name message } } }', {}, True),
        'programsProgram': ('query ($id: ID) { programsProgram(id: $id) { status errors { name message } } }', {'id': ids['program_public']}, True),
        'programsStudy': ('query ($id: ID!) { programsStudy(id: $id) { status errors { name message } } }', {'id': ids['study_public']}, True),
        'programsTrial': ('query ($id: ID) { programsTrial(id: $id) { status errors { name message } } }', {'id': ids['trial_public']}, True),
        'references': ('query ($ids: [ID!]) { references(ids: $ids) { status errors { name message } } }', {'ids': [ids['reference_public']]}, True),
        'referencesFileDownload': ('query ($id: ID!) { referencesFileDownload(fileId: $id) { status errors { name message } } }', {'id': public_file}, True),
        'referencesFileDownloadState': ('query ($id: ID!) { referencesFileDownloadState(fileId: $id) { status errors { name message } } }', {'id': public_file}, True),
        'referencesSearch': ('query { referencesSearch(description: "Readpolicy") { status errors { name message } } }', {}, True),
        'locationsRoots': ('query { locationsRoots { status errors { name message } } }', {}, True),
        'locationsCountries': ('query { locationsCountries { status errors { name message } } }', {}, True),
        'locationsDescendantsByType': ('query ($ids: [ID!]!) { locationsDescendantsByType(locationIds: $ids) { status errors { name message } } }', {'ids': [ids['country']]}, True),
        'locationsLocations': ('query ($ids: [ID!]!) { locationsLocations(ids: $ids) { status errors { name message } } }', {'ids': [ids['country']]}, True),
        'locationsSearch': ('query { locationsSearch(name: "a") { status errors { name message } } }', {}, True),
        'locationsLocationsByType': ('query ($id: ID!) { locationsLocationsByType(locationTypeId: $id) { status errors { name message } } }', {'id': ids['ontology_location_field']}, True),
    }


# the open fields, from the table itself (built with stand-in ids, as only the keys are wanted here)
OPEN_FIELDS = frozenset(open_queries(defaultdict(int), defaultdict(lambda: ('', b''))))

ACCOUNT_QUERIES = {
    'accountsAccount': 'query { accountsAccount { status errors { name message } } }',
    'accountsUserAccess': 'query { accountsUserAccess { status errors { name message } } }',
    'analysisRecentSubmissions': 'query { analysisRecentSubmissions { status errors { name message } } }',
    'analysisSubmission': 'query { analysisSubmission(id: "1") { status errors { name message } } }',
    'controlsControllers': 'query { controlsControllers(entityLabel: LOCATION, entityIds: ["1"]) { status errors { name message } } }',
    'controlsControlledCounts': 'query { controlsControlledCounts(teamIds: ["1"]) { status errors { name message } } }',
    'controlsControlledEntities': 'query { controlsControlledEntities(teamId: "1", label: LOCATION) { status errors { name message } } }',
    'controlsControlledUnits': 'query { controlsControlledUnits(teamId: "1") { status errors { name message } } }',
    'controlsTransfer': 'query { controlsTransfer(id: "1") { status errors { name message } } }',
    'controlsTransfers': 'query { controlsTransfers { status errors { name message } } }',
    'datasetsSubmission': 'query { datasetsSubmission(id: "1") { status errors { name message } } }',
    # place searches are asked of Nominatim by the server, so are not open to everyone
    'locationsGeocodeCountry': 'query { locationsGeocodeCountry(name: "Ireland") { status errors { name message } } }',
    'locationsSearchPlaces': 'query { locationsSearchPlaces(query: "Galway") { status errors { name message } } }',
    'ontologyAdmins': 'query { ontologyAdmins { status errors { name message } } }',
    'ontologyCommitHistory': 'query { ontologyCommitHistory { status errors { name message } } }',
    'ontologyEditors': 'query { ontologyEditors { status errors { name message } } }',
    'ontologyRoleRequests': 'query { ontologyRoleRequests { status errors { name message } } }',
    # no public directory of people or organisations: anonymous users meet no Persons at all, as Persons are released
    # at most to registered users and anonymous users get no contacts or contributors (docs/person.md §3)
    'people': 'query { people { status errors { name message } } }',
    'peoplePeople': 'query { peoplePeople(ids: ["1"]) { status errors { name message } } }',
    'peoplePerson': 'query { peoplePerson(id: "1") { status errors { name message } } }',
    'peopleClaimRequests': 'query { peopleClaimRequests { status errors { name message } } }',
    'peopleMyClaims': 'query { peopleMyClaims { status errors { name message } } }',
    'peopleMyPerson': 'query { peopleMyPerson { status errors { name message } } }',
    'referencesFileSubmission': 'query { referencesFileSubmission(fileId: "1") { status errors { name message } } }',
    'referencesRecentFiles': 'query { referencesRecentFiles { status errors { name message } } }',
    'teamsRoots': 'query { teamsRoots { status errors { name message } } }',
    'teamsTeam': 'query { teamsTeam(id: "1") { status errors { name message } } }',
    'teamsTeams': 'query { teamsTeams(ids: ["1"]) { status errors { name message } } }',
}


def test_every_query_is_classified(test_app):
    fields = set(test_app.graphql_schema.query_type.fields)
    classified = set(ACCOUNT_QUERIES) | set(OPEN_FIELDS)
    assert set(ACCOUNT_QUERIES).isdisjoint(OPEN_FIELDS)
    assert fields - classified == set(), "unclassified queries: add them to OPEN or ACCOUNT"
    assert classified - fields == set(), "queries in the table that are not in the schema"


@pytest.mark.asyncio(loop_scope="session")
async def test_open_queries_answer_anonymously(client, login_token_factory, read_policy):
    queries = open_queries(read_policy.ids, read_policy.files)
    assert set(queries) == OPEN_FIELDS
    for field, (query, variables, succeeds) in queries.items():
        response = await post_as(client, login_token_factory, None, query, variables)
        payload = get_verified_payload(response, field)
        errors = [(error['name'], error['message']) for error in payload['errors'] or []]
        assert AUTHENTICATION_ERROR not in errors, f"{field} refused an anonymous request"
        if succeeds:
            assert payload['status'] == GQLStatus.SUCCESS.name, f"{field}: {errors}"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('field', sorted(ACCOUNT_QUERIES))
async def test_account_queries_refuse_anonymous_requests(client, login_token_factory, field):
    response = await post_as(client, login_token_factory, None, ACCOUNT_QUERIES[field])
    payload = get_verified_payload(response, field)
    assert payload['status'] != GQLStatus.SUCCESS.name
    assert [(error['name'], error['message']) for error in payload['errors']] == [AUTHENTICATION_ERROR]
