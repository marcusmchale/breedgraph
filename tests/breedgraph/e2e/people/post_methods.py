from breedgraph.config import GQL_API_PATH
from tests.breedgraph.e2e.utils import with_auth

from typing import List

PERSON_FIELDS = (
    " id name basis informedAttestation orcid recordedAt erased erasedAt restricted "
    " teams { id } linkedUser { id } recordedBy { id } "
)

async def _post(client, token: str | None, query: str, variables: dict | None = None):
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables or {}}, headers=headers)

async def post_to_create_person(client, token: str, person: dict, control_team_id: int, release: str | None = None):
    return await _post(
        client, token,
        " mutation ( $person: PersonInput!, $controlTeamId: ID!, $release: ReadRelease ) { "
        "  peopleCreatePerson( person: $person, controlTeamId: $controlTeamId, release: $release ) { "
        "   status, result, errors { name, message } "
        "  } "
        " } ",
        {"person": person, "controlTeamId": control_team_id, "release": release}
    )

async def post_to_update_person(client, token: str, person: dict):
    return await _post(
        client, token,
        " mutation ( $person: PersonUpdate! ) { "
        "  peopleUpdatePerson( person: $person ) { status, result, errors { name, message } } "
        " } ",
        {"person": person}
    )

async def post_to_erase_person(client, token: str, person_id: int):
    return await _post(
        client, token,
        " mutation ( $id: ID! ) { peopleErasePerson( id: $id ) { status, result, errors { name, message } } } ",
        {"id": person_id}
    )

async def post_to_people(client, token: str, name: str | None = None):
    return await _post(
        client, token,
        f" query ( $name: String ) {{ people( name: $name ) {{ status, result {{ {PERSON_FIELDS} }}, errors {{ name, message }} }} }} ",
        {"name": name}
    )

async def post_to_people_by_ids(client, token: str, ids: List[int]):
    return await _post(
        client, token,
        f" query ( $ids: [ID!]! ) {{ peoplePeople( ids: $ids ) {{ status, result {{ {PERSON_FIELDS} }}, errors {{ name, message }} }} }} ",
        {"ids": ids}
    )

async def post_to_person(client, token: str, person_id: int):
    return await _post(
        client, token,
        f" query ( $id: ID! ) {{ peoplePerson( id: $id ) {{ status, result {{ {PERSON_FIELDS} }}, errors {{ name, message }} }} }} ",
        {"id": person_id}
    )
