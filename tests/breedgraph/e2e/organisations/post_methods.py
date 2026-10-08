from breedgraph.config import GQL_API_PATH
from tests.breedgraph.e2e.utils import with_auth

async def post_to_create_team(
    client,
    token:str,
    team: dict
):
    json = {
        "query": (
            " mutation ( "
            "  $team: TeamInput!"
            " ) { "
            "  organisationsCreateTeam( "
            "    team: $team, "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "team": team
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_organisations(client, token:str):
    json = {
        "query": (
            " query { "
            "  organisations {"
            "    status, "
            "    result { "
            "       name, "
            "       fullname, "
            "       id, "
            "       parent { "
            "           name,"
            "           fullname, "
            "           id, "
            "           children {name, fullname, id}"
            "       }, "
            "       children { "
            "           name, "
            "           fullname, "
            "           id, "
            "           parent {name, fullname, id}, "
            "           children {name, fullname, id}"
            "           affiliations { "
            "               read { user { id, name, fullname }, heritable, authorisation } "
            "               write { user { id, name, fullname }, heritable, authorisation } "
            "               admin { user { id, name, fullname }, heritable, authorisation } "
            "               curate { user { id, name, fullname }, heritable, authorisation } "
            "           }, "
            "           directAffiliations { "
            "               read { user { id, name, fullname }, heritable, authorisation } "
            "               write { user { id, name, fullname }, heritable, authorisation } "
            "               admin { user { id, name, fullname }, heritable, authorisation } "
            "               curate { user { id, name, fullname }, heritable, authorisation } "
            "           }, "
            "           inheritedAffiliations { "
            "               read { user { id, name, fullname }, heritable, authorisation } "
            "               write { user { id, name, fullname }, heritable, authorisation } "
            "               admin { user { id, name, fullname }, heritable, authorisation } "
            "               curate { user { id, name, fullname }, heritable, authorisation } "
            "           }, "
            "       }, "
            "       affiliations { "
            "           read { user { id, name, fullname }, heritable, authorisation } "
            "           write { user { id, name, fullname }, heritable, authorisation } "
            "           admin { user { id, name, fullname }, heritable, authorisation } "
            "           curate { user { id, name, fullname }, heritable, authorisation } "
            "       }, "
            "       directAffiliations { "
            "           read { user { id, name, fullname }, heritable, authorisation } "
            "           write { user { id, name, fullname }, heritable, authorisation } "
            "           admin { user { id, name, fullname }, heritable, authorisation } "
            "           curate { user { id, name, fullname }, heritable, authorisation } "
            "       }, "
            "       inheritedAffiliations { "
            "           read { user { id, name, fullname }, heritable, authorisation } "
            "           write { user { id, name, fullname }, heritable, authorisation } "
            "           admin { user { id, name, fullname }, heritable, authorisation } "
            "           curate { user { id, name, fullname }, heritable, authorisation } "
            "       }, "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        )
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_team(client, token:str, team_id: int):
    json = {
        "query": (
            " query ("
            "   $id : ID!"
            " ) { "
            "  organisationsTeam ( "
            "  id: $id,"
            "  ) {"
            "    status, "
            "    result { "
            "       name, "
            "       fullname, "
            "       id, "
            "       parent { "
            "           name,"
            "           fullname, "
            "           id, "
            "           children {name, fullname, id}"
            "       }, "
            "       children { "
            "           name, "
            "           fullname, "
            "           id, "
            "           parent {name, fullname, id}"
            "       }, "
            "       affiliations { "
            "           read { user { id, name, fullname }} "
            "           write { user { id, name, fullname }} "
            "           admin { user { id, name, fullname }} "
            "           curate { user { id, name, fullname }} "
            "       }, "
            "       directAffiliations { "
            "           read { user { id, name, fullname }} "
            "           write { user { id, name, fullname }} "
            "           admin { user { id, name, fullname }} "
            "           curate { user { id, name, fullname }} "
            "       }, "
            "       inheritedAffiliations { "
            "           read { user { id, name, fullname }} "
            "           write { user { id, name, fullname }} "
            "           admin { user { id, name, fullname }} "
            "           curate { user { id, name, fullname }} "
            "       }, "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "id": team_id,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_delete_team(client, token:str, team_id: int):
    json = {
        "query": (
            " mutation ( "
            "  $id: ID!"
            " ) { "
            "  organisationsDeleteTeam( "
            "    id: $id "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "id": team_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_update_team(client, token:str, team: dict):
    json = {
        "query": (
            " mutation ( "
            "  $team: TeamUpdate! "
            " ) { "
            "  organisationsUpdateTeam( "
            "    team: $team "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "team": team
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def _post(client, token: str | None, query: str, variables: dict | None = None):
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables or {}}, headers=headers)

async def post_to_data_processing_terms(client, token: str | None = None):
    return await _post(
        client, token,
        " query { organisationsDataProcessingTerms { status, result { version, url }, errors { name, message } } } "
    )

async def post_to_declare_legal_entity(client, token: str, team_id: int, legal_entity: dict):
    return await _post(
        client, token,
        " mutation ( $teamId: ID!, $legalEntity: LegalEntityInput! ) { "
        "  organisationsDeclareLegalEntity( teamId: $teamId, legalEntity: $legalEntity ) { "
        "   status, result, errors { name, message } "
        "  } "
        " } ",
        {"teamId": team_id, "legalEntity": legal_entity}
    )

async def post_to_team_legal_entity(client, token: str, team_id: int):
    return await _post(
        client, token,
        " query ( $id: ID! ) { organisationsTeam( id: $id ) { "
        "  status, "
        "  result { id, name, legalEntity { legalName, privacyContact, termsVersion, declaredAt, declaredBy { id } } }, "
        "  errors { name, message } "
        " } } ",
        {"id": team_id}
    )
