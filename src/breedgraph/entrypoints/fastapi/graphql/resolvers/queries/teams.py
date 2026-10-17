from ariadne import ObjectType

from typing import List

from breedgraph import config
from breedgraph.domain.model.team_trees import TeamOutput

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_users_map,
    update_teams_map
)

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

team = ObjectType("Team")
legal_entity = ObjectType("LegalEntity")
affiliations = ObjectType("Affiliations")
affiliation = ObjectType("Affiliation")
user = ObjectType("User")
graphql_resolvers.register_type_resolvers(team, legal_entity, affiliations, affiliation, user)

# Teams are for signed-in users (docs/read-access.md, rule 9): anonymous users see no team trees. Who holds a Person
# record is shown with the Person instead (Person.dataController), so the organisations using BreedGraph are not listed
# publicly.

@graphql_query.field("teamsRoots")
@graphql_payload
@require_authentication
async def get_team_trees(_, info) -> List[TeamOutput]:
    """Every team tree root, with its legal entity, and the teams in it the user is affiliated with"""
    await update_teams_map(info.context)
    teams_map = info.context.get('teams_map')
    team_tree_roots = info.context.get('team_tree_roots')
    return [teams_map.get(i) for i in team_tree_roots]

def _team_asked_for(teams_map: dict, team_id: int) -> TeamOutput | None:
    """
    A team asked for by id: the team, or a placeholder for one hidden from the user, its id and a REDACTED name (see
    docs/read-access.md, rule 2). The teams map gives a hidden team's stand-in, which serves references, not this.
    """
    team = teams_map.get(team_id)
    if team is None:
        return None
    if team.id != team_id:
        return TeamOutput(id=team_id, name='REDACTED', fullname='REDACTED')
    return team

@graphql_query.field("teamsTeam")
@graphql_payload
@require_authentication
async def get_team(_, info, id: int) -> TeamOutput:
    await update_teams_map(info.context, team_ids=[id])
    return _team_asked_for(info.context.get('teams_map'), id)

@graphql_query.field("teamsTeams")
@graphql_payload
@require_authentication
async def get_teams(_, info, ids: List[int]) -> List[TeamOutput]:
    await update_teams_map(info.context, team_ids=ids)
    teams_map = info.context.get('teams_map')
    return [team for team in (_team_asked_for(teams_map, team_id) for team_id in ids) if team is not None]

@graphql_query.field("teamsDataProcessingTerms")
@graphql_payload
async def get_data_processing_terms(_, info) -> dict:
    return {
        'version': config.DATA_PROCESSING_TERMS_VERSION,
        'url': config.DATA_PROCESSING_TERMS_URL
    }

@legal_entity.field("declaredBy")
async def resolve_declared_by(obj, info):
    if obj.declared_by is None:
        return None
    await update_users_map(info.context, user_ids=[obj.declared_by])
    return info.context.get('users_map', {}).get(obj.declared_by)

@team.field("parent")
def resolve_parent(obj, info):
    return info.context.get('teams_map').get(obj.parent)

@team.field("children")
def resolve_children(obj, info):
    return [info.context.get('teams_map').get(child) for child in obj.children]

@team.field("affiliations")
async def resolve_affiliations(obj, info):
    return obj.affiliations

@affiliations.field("read")
def resolve_read(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.read.items()
    ]

@affiliations.field("write")
def resolve_write(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.write.items()
    ]

@affiliations.field("curate")
def resolve_curate(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.curate.items()
    ]
@affiliations.field("admin")
def resolve_admin(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.admin.items()
    ]

@affiliation.field("user")
async def resolve_user(obj, info):
    await update_users_map(info.context, user_ids=[obj.get('user')])
    return info.context.get('users_map', {}).get(obj.get('user'))
