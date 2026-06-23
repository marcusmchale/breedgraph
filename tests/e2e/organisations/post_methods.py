from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth

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
            "               read { user { id, name, fullname, email }, heritable, authorisation } "
            "               write { user { id, name, fullname, email }, heritable, authorisation } "
            "               admin { user { id, name, fullname, email }, heritable, authorisation } "
            "               curate { user { id, name, fullname, email }, heritable, authorisation } "
            "           }, "
            "           directAffiliations { "
            "               read { user { id, name, fullname, email }, heritable, authorisation } "
            "               write { user { id, name, fullname, email }, heritable, authorisation } "
            "               admin { user { id, name, fullname, email }, heritable, authorisation } "
            "               curate { user { id, name, fullname, email }, heritable, authorisation } "
            "           }, "
            "           inheritedAffiliations { "
            "               read { user { id, name, fullname, email }, heritable, authorisation } "
            "               write { user { id, name, fullname, email }, heritable, authorisation } "
            "               admin { user { id, name, fullname, email }, heritable, authorisation } "
            "               curate { user { id, name, fullname, email }, heritable, authorisation } "
            "           }, "
            "       }, "
            "       affiliations { "
            "           read { user { id, name, fullname, email }, heritable, authorisation } "
            "           write { user { id, name, fullname, email }, heritable, authorisation } "
            "           admin { user { id, name, fullname, email }, heritable, authorisation } "
            "           curate { user { id, name, fullname, email }, heritable, authorisation } "
            "       }, "
            "       directAffiliations { "
            "           read { user { id, name, fullname, email }, heritable, authorisation } "
            "           write { user { id, name, fullname, email }, heritable, authorisation } "
            "           admin { user { id, name, fullname, email }, heritable, authorisation } "
            "           curate { user { id, name, fullname, email }, heritable, authorisation } "
            "       }, "
            "       inheritedAffiliations { "
            "           read { user { id, name, fullname, email }, heritable, authorisation } "
            "           write { user { id, name, fullname, email }, heritable, authorisation } "
            "           admin { user { id, name, fullname, email }, heritable, authorisation } "
            "           curate { user { id, name, fullname, email }, heritable, authorisation } "
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
            "   $teamId : Int!"
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
            "           read { user { id, name, fullname, email }} "
            "           write { user { id, name, fullname, email }} "
            "           admin { user { id, name, fullname, email }} "
            "           curate { user { id, name, fullname, email }} "
            "       }, "
            "       directAffiliations { "
            "           read { user { id, name, fullname, email }} "
            "           write { user { id, name, fullname, email }} "
            "           admin { user { id, name, fullname, email }} "
            "           curate { user { id, name, fullname, email }} "
            "       }, "
            "       inheritedAffiliations { "
            "           read { user { id, name, fullname, email }} "
            "           write { user { id, name, fullname, email }} "
            "           admin { user { id, name, fullname, email }} "
            "           curate { user { id, name, fullname, email }} "
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
            "  $teamId: Int!"
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
