from src.breedgraph.domain.model.controls import Access
from src.breedgraph.domain.model.ontology import Version
from src.breedgraph.custom_exceptions import InconsistentStateError

from typing import List, Set

async def update_ontology_map(context, entry_ids: List[int] = None, version: int = None):
    user_id = context.get('user_id')
    bus = context.get('bus')
    async with bus.uow.get_uow(user_id = user_id) as uow:
        if not 'ontology_version' in context:
            if version:
                context['ontology_version'] = Version.from_packed(version)
            else:
                context['ontology_version'] = await uow.ontology.get_current_version()
        elif version is not None:
            if Version.from_packed(version) != context.get('ontology_version'):
                # this should only happen if the front end is specifying a version, then changing that.
                # normally the version is set once, the first time this is called and never changed again.
                raise InconsistentStateError('Ontology version changed during the request')

        version = context.get('ontology_version')
        if not 'ontology_entries' in context:
            context['ontology_entries'] = dict()

        entries_to_update = [
            entry_id for entry_id in entry_ids or [] if entry_id not in context['ontology_entries']
        ]
        async for entry in uow.ontology.get_entries(version=version, entry_ids=entries_to_update, as_output=True):
            context['ontology_entries'][entry.id] = entry

async def update_teams_map(context, team_ids: List[int] | Set[int] | None = None):
    user_id = context.get('user_id')
    bus = context.get('bus')

    teams_map = context.get('teams_map', dict())
    organisation_roots = context.get('organisation_roots', list())

    # if called with teams = None, retrieve all organisations
    if team_ids is None:
        async with bus.uow.get_uow(user_id=user_id) as uow:
            async for org in uow.repositories.organisations.get_all():
                teams_map.update(org.to_output_map())
                organisation_roots.append(org.root.id)

    else:
        if isinstance(team_ids, list):
            team_ids = set(team_ids)
        unmapped = team_ids - set(teams_map.keys())
        if unmapped:
            async with bus.uow.get_uow(user_id=user_id) as uow:
                async for org in uow.repositories.organisations.get_all(team_ids=team_ids):
                    if org is not None:
                        teams_map.update(org.to_output_map())
                        org_root = org.root
                        if not org_root in organisation_roots:
                            organisation_roots.append(org_root)

    context['teams_map'] = teams_map
    context['organisation_roots'] = organisation_roots

async def update_users_map(context, user_ids: List[int] | None = None):
    agent_id = context.get('user_id')
    bus = context.get('bus')

    users_map = context.get('users_map', dict())
    user_ids = set(user_ids) if user_ids is not None else set()
    unmapped = user_ids - set(users_map.keys())
    if unmapped:
        async with bus.uow.get_uow(user_id = agent_id) as uow:
            agent_access_teams = await uow.views.access_teams(user=agent_id)
            agent_admin_teams = agent_access_teams[Access.ADMIN]
            async for account in uow.repositories.accounts.get_all(users = list(user_ids), teams=agent_admin_teams):
                users_map[account.user.id] = account.user
    context['users_map'] = users_map

async def update_locations_map(context, location_id: int | None = None):
    user = context.get('user_id')
    bus = context.get('bus')

    locations_map = context.get('locations_map', dict())
    region_roots = context.get('region_roots', list())

    if location_id is None and not locations_map:
        async with bus.uow.get_uow(user=user) as uow:
            async for region in uow.repositories.regions.get_all():
                locations_map.update(region.to_output_map())
                region_roots.append(region.root.id)

    if location_id is not None and not location_id in locations_map:
        async with bus.uow.get_uow(user=user) as uow:
            region = await uow.repositories.regions.get(location=location_id)
            if region is not None:
                locations_map.update(region.to_output_map())
                region_root = region.get_root()
                if not region_root in region_roots:
                    region_roots.append(region_root)

    context['locations_map'] = locations_map
    context['region_roots'] = region_roots

async def update_layouts_map(context, location_id: int | None = None, layout_id: int | None = None):
    user = context.get('user_id')
    bus = context.get('bus')

    layouts_map = context.get('layouts_map', dict())
    arrangement_roots = context.get('arrangement_roots', list())

    if layout_id is None and not layouts_map:
        async with bus.uow.get_uow(user=user) as uow:
            async for arrangement in uow.repositories.arrangements.get_all(location=location_id):
                layouts_map.update(arrangement.to_output_map())
                arrangement_roots.append(arrangement.root.id)

    if layout_id is not None and not layout_id in layouts_map:
        async with bus.uow.get_uow(user=user) as uow:
            arrangement = await uow.repositories.arrangements.get(layout=layout_id)
            if arrangement is not None:
                layouts_map.update(arrangement.to_output_map())
                arrangement_root = arrangement.get_root()
                if not arrangement_root in arrangement_roots:
                    arrangement_roots.append(arrangement_root)

    context['layouts_map'] = layouts_map
    context['arrangement_roots'] = arrangement_roots

async def update_units_map(context, location_id: int | None = None, unit_id: int | None = None):
    user = context.get('user_id')
    bus = context.get('bus')

    units_map = context.get('units_map', dict())
    block_roots = context.get('block_roots', list())

    if unit_id is None and not units_map:
        async with bus.uow.get_uow(user=user) as uow:
            async for block in uow.repositories.blocks.get_all(location=location_id):
                units_map.update(block.to_output_map())
                block_roots.append(block.root.id)

    if unit_id is not None and not unit_id in units_map:
        async with bus.uow.get_uow(user=user) as uow:
            block = await uow.repositories.blocks.get(unit=unit_id)
            if block is not None:
                units_map.update(block.to_output_map())
                block_root = block.get_root()
                if not block_root in block_roots:
                    block_roots.append(block_root)

    context['units_map'] = units_map
    context['block_roots'] = block_roots

async def update_programs_map(
        context,
        program_id: int | None = None,
        trial_id: int | None = None,
        study_id: int | None = None
):
    user = context.get('user_id')
    bus = context.get('bus')

    programs_map = context.get('programs_map', dict())

    if program_id is None and not programs_map:
        async with bus.uow.get_uow(user=user) as uow:
            async for program_id in uow.repositories.programs.get_all():
                programs_map.update(program_id.to_output_map())
    elif program_id is not None and not program_id in programs_map:
        async with bus.uow.get_uow(user=user) as uow:
            program_id = await uow.repositories.programs.get(program=program_id)
            programs_map.update(program_id.to_output_map())
    if trial_id is not None:
        for program_id, program_id in programs_map.values():
            if trial_id in program_id.trials:
                break
        else:
            async with bus.uow.get_uow(user=user) as uow:
                program_id = await uow.repositories.programs.get(trial=trial_id)
                programs_map.update(program_id.to_output_map())
    if study_id is not None:
        for program_id, program_id in programs_map.values():
            for trial_id, trial_id in program_id.trials.items():
                if study_id in trial_id.studies:
                    break
            else:
                async with bus.uow.get_uow(user=user) as uow:
                    program_id = await uow.repositories.programs.get(study=study_id)
                    programs_map.update(program_id.to_output_map())
                break

    context['programs_map'] = programs_map
