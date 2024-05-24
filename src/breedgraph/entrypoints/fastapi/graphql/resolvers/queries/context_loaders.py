from src.breedgraph import views

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

async def inject_users_map(context):
    if 'users_map' in context:
        return

    a = context.get('account')
    if a is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    users_map = dict()
    async for user in views.accounts.users(context['bus'].uow, user=a.user.id):
        users_map[user.id] = user

    # insert the accounts map into the context for building responses in the resolver
    context['users_map'] = users_map

async def inject_teams_map(context):
    if 'teams_map' in context:
        return

    a = context.get('account')
    if a is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    # insert the team map into the context for building parent/child relationships in the resolver
    teams_map = dict()
    async for t in views.accounts.teams(context['bus'].uow, user=a.user.id):
        teams_map[t.id] = t
    context['teams_map'] = teams_map
