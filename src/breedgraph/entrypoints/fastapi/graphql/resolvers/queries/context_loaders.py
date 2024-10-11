from src.breedgraph import views

async def inject_users_map(context):
    if 'users_map' in context:
        return

    user_id = context.get('user_id')

    users_map = dict()
    async for user in views.accounts.users(context['bus'].uow, user=user_id):
        users_map[user.id] = user

    context['users_map'] = users_map

async def inject_ontology(context, version_id: int = None, entry_id: int = None):
    if 'ontology' in context:
        if version_id is None and entry_id is None:
            return

        ontology = context.get('ontology')
        if ontology.version.id == version_id or entry_id in ontology.entries:
            return

    bus = context.get('bus')
    async with bus.uow.get_repositories() as uow:
        ontology = await uow.ontologies.get(version_id=version_id, entry_id=entry_id)
        context['ontology'] = ontology

async def update_teams_map(context, team_id: int|None = None):
    user_id = context.get('user_id')
    bus = context.get('bus')

    teams_map = context.get('teams_map', dict())
    organisation_roots = context.get('organisation_roots', list())

    if team_id is None and not teams_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            async for org in uow.organisations.get_all():
                teams_map.update(org.to_output_map())
                organisation_roots.append(org.root.id)

    if team_id is not None and not team_id in teams_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            organisation = await uow.organisations.get(team_id=team_id)
            if organisation is not None:
                teams_map.update(organisation.to_output_map())
                organisation_root_id = organisation.get_root_id()
                if not organisation_root_id in organisation_roots:
                    organisation_roots.append(organisation_root_id)

    context['teams_map'] = teams_map
    context['organisation_roots'] = organisation_roots


async def update_locations_map(context, location_id: int|None = None):
    user_id = context.get('user_id')
    bus = context.get('bus')

    locations_map = context.get('locations_map', dict())
    region_roots = context.get('region_roots', list())

    if location_id is None and not locations_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            async for region in uow.regions.get_all():
                locations_map.update(region.to_output_map())
                region_roots.append(region.root.id)

    if location_id is not None and not location_id in locations_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            region = await uow.regions.get(location_id=location_id)
            if region is not None:
                locations_map.update(region.to_output_map())
                region_root_id = region.get_root_id()
                if not region_root_id in region_roots:
                    region_roots.append(region_root_id)

    context['locations_map'] = locations_map
    context['region_roots'] = region_roots

async def update_layouts_map(context, location_id: int | None = None, layout_id: int | None = None):
    user_id = context.get('user_id')
    bus = context.get('bus')

    layouts_map = context.get('layouts_map', dict())
    arrangement_roots = context.get('arrangement_roots', list())

    if layout_id is None and not layouts_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            async for arrangement in uow.arrangements.get_all(location_id=location_id):
                layouts_map.update(arrangement.to_output_map())
                arrangement_roots.append(arrangement.root.id)

    if layout_id is not None and not layout_id in layouts_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            arrangement = await uow.arrangements.get(layout_id=layout_id)
            if arrangement is not None:
                layouts_map.update(arrangement.to_output_map())
                arrangement_root_id = arrangement.get_root_id()
                if not arrangement_root_id in arrangement_roots:
                    arrangement_roots.append(arrangement_root_id)

    context['layouts_map'] = layouts_map
    context['arrangement_roots'] = arrangement_roots

async def update_units_map(context, location_id: int | None = None, unit_id: int | None = None):
    user_id = context.get('user_id')
    bus = context.get('bus')

    units_map = context.get('units_map', dict())
    block_roots = context.get('block_roots', list())

    if unit_id is None and not units_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            async for block in uow.blocks.get_all(location_id=location_id):
                units_map.update(block.to_output_map())
                block_roots.append(block.root.id)

    if unit_id is not None and not unit_id in units_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            block = await uow.blocks.get(unit_id=unit_id)
            if block is not None:
                units_map.update(block.to_output_map())
                block_root_id = block.get_root_id()
                if not block_root_id in block_roots:
                    block_roots.append(block_root_id)

    context['units_map'] = units_map
    context['block_roots'] = block_roots