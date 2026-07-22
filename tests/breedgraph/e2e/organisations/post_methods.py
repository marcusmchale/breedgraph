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
            "   $teamId : ID!"
            " ) { "
            "  organisationsTeam ( "
            "  teamId: $teamId,"
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
            "teamId": team_id,
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
            "  $teamId: ID!"
            " ) { "
            "  organisationsDeleteTeam( "
            "    teamId: $teamId "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "teamId": team_id
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
