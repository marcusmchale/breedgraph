from src.breedgraph import views

from src.breedgraph.custom_exceptions import UnauthorisedOperationError


async def inject_teams_map(context):
    if 'teams_map' in context:
        return

    user_id = context.get('user_id')
    bus = context.get('bus')
    teams_map = dict()
    organisation_roots = list()

    async with bus.uow.get_repositories(user_id=user_id) as uow:
        async for org in uow.organisations.get_all():
            teams_map.update(org.to_output_map())
            organisation_roots.append(org.root.id)

    context['teams_map'] = teams_map
    context['organisation_roots'] = organisation_roots

async def inject_users_map(context):
    if 'users_map' in context:
        return

    user_id = context.get('user_id')

    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    users_map = dict()
    async for user in views.accounts.users(context['bus'].uow, user=user_id):
        users_map[user.id] = user

    # insert the accounts map into the context for building responses in the resolver
    context['users_map'] = users_map



