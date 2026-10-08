from breedgraph.config import GQL_API_PATH
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from tests.breedgraph.e2e.utils import with_auth

from typing import List

async def post_to_set_release(
        client,
        token: str,
        entity_label: ControlledModelLabel,
        entity_ids: List[int],
        release: ReadRelease
):
    json={
        "query": (
            " mutation ( $entityLabel: ControlledModelLabel!, $entityIds: [ID!]!, $release: ReadRelease!) { "
            "  controlsSetRelease( "
            "   entityLabel: $entityLabel  "
            "   entityIds: $entityIds "
            "   release: $release "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "entityLabel" : entity_label.name,
            "entityIds" : entity_ids,
            "release" : release.name
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_controllers(
        client,
        token: str,
        entity_label: ControlledModelLabel,
        entity_ids: List[int]
):
    json={
        "query": (
            " query ( $entityLabel: ControlledModelLabel!, $entityIds: [ID!]!) { "
            "  controlsControllers( "
            "   entityLabel: $entityLabel  "
            "   entityIds: $entityIds "
            "  ) { "
            "    status, "
            "    result {"
            "       controls { team {name, id}, release, time }, "
            "       writes { user {id, name } time } "
            "       teams { name, id } "
            "       release "
            "       created "
            "       updated "
            "   }"
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "entityLabel" : entity_label.name,
            "entityIds" : entity_ids
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def _post(client, token: str, query: str, variables: dict):
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables}, headers=headers)

CONTROL_TRANSFER_FIELDS = (
    " id status keepFromTeams release offeredAt acceptedAt rejectedAt cancelledAt "
    " entities { label id } "
    " fromTeams { id name } "
    " recipientTeam { id name } "
    " toTeams { id name } "
)

async def post_to_offer_transfer(client, token: str, offer: dict):
    return await _post(
        client, token,
        " mutation ( $offer: ControlTransferOffer! ) { "
        "  controlsOfferTransfer( offer: $offer ) { status, result, errors { name, message } } "
        " } ",
        {"offer": offer}
    )

async def post_to_accept_transfer(client, token: str, transfer_id: int, to_team_ids: List[int], release: ReadRelease | None = None):
    return await _post(
        client, token,
        " mutation ( $id: ID!, $toTeamIds: [ID!]!, $release: ReadRelease ) { "
        "  controlsAcceptTransfer( id: $id, toTeamIds: $toTeamIds, release: $release ) { status, result, errors { name, message } } "
        " } ",
        {"id": transfer_id, "toTeamIds": to_team_ids, "release": release.name if release else None}
    )

async def post_to_reject_transfer(client, token: str, transfer_id: int):
    return await _post(
        client, token,
        " mutation ( $id: ID! ) { controlsRejectTransfer( id: $id ) { status, result, errors { name, message } } } ",
        {"id": transfer_id}
    )

async def post_to_cancel_transfer(client, token: str, transfer_id: int):
    return await _post(
        client, token,
        " mutation ( $id: ID! ) { controlsCancelTransfer( id: $id ) { status, result, errors { name, message } } } ",
        {"id": transfer_id}
    )

async def post_to_renounce_control(client, token: str, entities: List[dict], team_ids: List[int]):
    return await _post(
        client, token,
        " mutation ( $entities: [ControlledEntityInput!]!, $teamIds: [ID!]! ) { "
        "  controlsRenounceControl( entities: $entities, teamIds: $teamIds ) { status, result, errors { name, message } } "
        " } ",
        {"entities": entities, "teamIds": team_ids}
    )

async def post_to_transfers(client, token: str, statuses: List[str] | None = None):
    return await _post(
        client, token,
        " query ( $statuses: [ControlTransferStatus!] ) { "
        f"  controlsTransfers( statuses: $statuses ) {{ status, result {{ {CONTROL_TRANSFER_FIELDS} }}, errors {{ name, message }} }} "
        " } ",
        {"statuses": statuses}
    )

async def post_to_transfer(client, token: str, transfer_id: int):
    return await _post(
        client, token,
        " query ( $id: ID! ) { "
        f"  controlsTransfer( id: $id ) {{ status, result {{ {CONTROL_TRANSFER_FIELDS} }}, errors {{ name, message }} }} "
        " } ",
        {"id": transfer_id}
    )
