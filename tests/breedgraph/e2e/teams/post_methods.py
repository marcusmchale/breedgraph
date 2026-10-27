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
            "  teamsCreateTeam( "
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

async def post_to_teams_roots(client, token:str):
    json = {
        "query": (
            " query { "
            "  teamsRoots {"
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
            "               read { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               write { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               admin { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               curate { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           }, "
            "           directAffiliations { "
            "               read { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               write { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               admin { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               curate { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           }, "
            "           inheritedAffiliations { "
            "               read { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               write { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               admin { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "               curate { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           }, "
            "       }, "
            "       affiliations { "
            "           read { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           write { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           admin { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           curate { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "       }, "
            "       directAffiliations { "
            "           read { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           write { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           admin { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           curate { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "       }, "
            "       inheritedAffiliations { "
            "           read { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           write { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           admin { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
            "           curate { user { id, name, fullname }, heritable, heritableRequested, authorisation } "
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
            "  teamsTeam ( "
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
            "  teamsDeleteTeam( "
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
            "  teamsUpdateTeam( "
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
