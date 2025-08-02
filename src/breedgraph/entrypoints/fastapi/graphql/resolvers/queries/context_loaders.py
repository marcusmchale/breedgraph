from src.breedgraph.domain.model.controls import Access

from typing import List, Set

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

async def update_teams_map(context, team_ids: List[int]|Set[int]|None = None):
    user_id = context.get('user_id')
    bus = context.get('bus')

    teams_map = context.get('teams_map', dict())
    organisation_roots = context.get('organisation_roots', list())

    # if called with team_ids = None, retrieve all organisations
    if team_ids is None:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            async for org in uow.organisations.get_all():
                teams_map.update(org.to_output_map())
                organisation_roots.append(org.root.id)

    else:
        if isinstance(team_ids, list):
            team_ids = set(team_ids)
        unmapped = team_ids - set(teams_map.keys())
        if unmapped:
            async with bus.uow.get_repositories(user_id=user_id) as uow:
                async for org in uow.organisations.get_all(team_ids=team_ids):
                    if org is not None:
                        teams_map.update(org.to_output_map())
                        org_root_id = org.get_root_id()
                        if not org_root_id in organisation_roots:
                            organisation_roots.append(org_root_id)

    context['teams_map'] = teams_map
    context['organisation_roots'] = organisation_roots

async def update_users_map(context, user_ids: List[int]|None = None):
    agent_id = context.get('user_id')
    bus = context.get('bus')

    users_map = context.get('users_map', dict())
    user_ids = set(user_ids) if user_ids is not None else set()
    unmapped = user_ids - set(users_map.keys())
    if unmapped:
        async with bus.uow.get_views() as views_holder:
            agent_access_teams = await views_holder.access_teams(user=agent_id)
            agent_admin_teams = agent_access_teams[Access.ADMIN]
        async with bus.uow.get_repositories(user_id=agent_id) as uow:
            async for account in uow.accounts.get_all(user_ids = list(user_ids), team_ids=agent_admin_teams):
                users_map[account.user.id] = account.user
    context['users_map'] = users_map

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

async def update_programs_map(
        context,
        program_id: int | None = None,
        trial_id: int | None = None,
        study_id: int | None = None
):
    user_id = context.get('user_id')
    bus = context.get('bus')

    programs_map = context.get('programs_map', dict())

    if program_id is None and not programs_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            async for program in uow.programs.get_all():
                programs_map.update(program.to_output_map())
    elif program_id is not None and not program_id in programs_map:
        async with bus.uow.get_repositories(user_id=user_id) as uow:
            program = await uow.programs.get(program_id=program_id)
            programs_map.update(program.to_output_map())
    if trial_id is not None:
        for program_id, program in programs_map.values():
            if trial_id in program.trials:
                break
        else:
            async with bus.uow.get_repositories(user_id=user_id) as uow:
                program = await uow.programs.get(trial_id=trial_id)
                programs_map.update(program.to_output_map())
    if study_id is not None:
        for program_id, program in programs_map.values():
            for trial_id, trial in program.trials.items():
                if study_id in trial.studies:
                    break
            else:
                async with bus.uow.get_repositories(user_id=user_id) as uow:
                    program = await uow.programs.get(study_id=study_id)
                    programs_map.update(program.to_output_map())
                break

    context['programs_map'] = programs_map
