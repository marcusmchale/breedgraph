import asyncio
from src.breedgraph.domain.model.accounts import UserOutput
from src.breedgraph.domain.model.controls import Access
from src.breedgraph.domain.model.ontology import Version, OntologyEntryLabel, LifecyclePhase
from src.breedgraph.custom_exceptions import InconsistentStateError

from typing import List, Set

import logging

logger = logging.getLogger(__name__)

# Helper functions to get or create locks for each map type to prevent concurrent updates

def _get_lock(context, lock_name: str):
    """Get or create a lock for a specific map in this context"""
    if lock_name not in context:
        context[lock_name] = asyncio.Lock()
    return context[lock_name]

async def update_ontology_version_context(context, version: Version = None):
    context_version = context.get('ontology_version')
    if version:
        if context_version:
            if context_version == version:
                return
            else:
                raise InconsistentStateError('Ontology version must be consistent within the request context')
        else:
            context['ontology_version'] = version
    else:
        if context_version:
            return
        else:
            bus = context.get('bus')
            user_id = context.get('user_id') # This might be None for unauthenticated requests
            async with bus.uow.get_uow(user_id=user_id) as uow:
                context['ontology_version'] = await uow.ontology.get_current_version()

async def update_ontology_map(
        context,
        entry_ids: List[int] = None,
        phases: List[LifecyclePhase] = None,
        version: Version = None,
        names: List[str] = None,
        labels: List[OntologyEntryLabel] = None
):
    async with _get_lock(context, '_ontology_lock'):
        bus = context.get('bus')
        user_id = context.get('user_id')  # This might be None for unauthenticated requests
        await update_ontology_version_context(context, version)
        async with bus.uow.get_uow(user_id=user_id) as uow:
            version = context.get('ontology_version')
            if not 'ontology_map' in context:
                context['ontology_map'] = dict()

            entries_to_update = [
                entry_id for entry_id in entry_ids or [] if entry_id not in context['ontology_map']
            ]
            async for entry in uow.ontology.get_entries(
                version=version,
                entry_ids=entries_to_update,
                phases=phases,
                names=names,
                labels=labels,
                as_output=True
            ):
                context['ontology_map'][entry.id] = entry

async def update_teams_map(context, team_ids: List[int] | Set[int] | None = None):
    async with _get_lock(context, '_teams_lock'):
        bus = context.get('bus')
        user_id = context.get('user_id')  # This might be None for unauthenticated requests
        teams_map = context.get('teams_map', dict())
        organisation_roots = context.get('organisation_roots', list())
        logger.debug('Updating teams map for user ' + str(user_id) + ' with team ids: ' + str(team_ids) + '')
        async with bus.uow.get_uow(user_id=user_id) as uow:
            # if called with teams = None, retrieve all organisations
            if team_ids is None:
                async for org in uow.repositories.organisations.get_all():
                    teams_map.update(org.to_output_map())
                    organisation_roots.append(org.root.id)
            else:
                if isinstance(team_ids, list):
                    team_ids = set(team_ids)
                unmapped = team_ids - set(teams_map.keys())
                if unmapped:
                    n = 0
                    async for org in uow.repositories.organisations.get_all(team_ids=team_ids):
                        if org is not None:
                            n+=1
                            logger.debug(f"Updating teams map with {org.root.id} for {user_id} at {n}")
                            logger.debug(f"Teams map: {teams_map}")
                            teams_map.update(org.to_output_map())
                            logger.debug(f"Teams map after update: {teams_map}")
                            org_root = org.root
                            if not org_root in organisation_roots:
                                organisation_roots.append(org_root)

            context['teams_map'] = teams_map
            context['organisation_roots'] = organisation_roots

async def update_users_map(context, user_ids: List[int] | None = None):
    async with _get_lock(context, '_users_lock'):

        bus = context.get('bus')
        agent_id = context.get('user_id')  # This might be None for unauthenticated requests
        users_map = context.get('users_map', dict())

        async with bus.uow.get_uow(user_id=agent_id) as uow:
            user_ids = set(user_ids) if user_ids is not None else set()
            unmapped = list(user_ids - set(users_map.keys()))
            if unmapped:
                team_ids = list(uow.controls.access_teams.get(Access.ADMIN))
                async for user_for_admin in uow.views.accounts.get_users_for_admin(team_ids = team_ids, user_ids=unmapped):
                    users_map[user_for_admin.id] = user_for_admin

            # agents can always see their own account
            if agent_id in user_ids and not agent_id in users_map:
                agent = await uow.views.accounts.get_user(user_id=agent_id)
                users_map[agent_id] = agent

            # Present redacted users, with only the ID property (whether real or not)
            for user_id in user_ids:
                if not user_id in users_map:
                    users_map[user_id] = UserOutput(
                        id=user_id
                    )

        context['users_map'] = users_map

async def update_locations_map(context, location_ids: List[int] | None = None):
    async with _get_lock(context, '_locations_lock'):
        bus = context.get('bus')
        user_id = context.get('user_id')  # This might be None for unauthenticated requests

        async with bus.uow.get_uow(user_id=user_id) as uow:
            locations_map = context.get('locations_map', dict())
            region_roots = context.get('region_roots', list())

            if location_ids is None:
                if not locations_map:
                    async for region in uow.repositories.regions.get_all():
                        locations_map.update(region.to_output_map())
                        region_roots.append(region.root.id)
                else:
                    pass
            else:
                for location_id in location_ids:
                    if not location_id in locations_map:
                        region = await uow.repositories.regions.get(location_id=location_id)
                        if region is not None:
                            locations_map.update(region.to_output_map())
                            region_root = region.root
                            if not region_root in region_roots:
                                region_roots.append(region_root)

            context['locations_map'] = locations_map
            context['region_roots'] = region_roots

async def update_layouts_map(context, location_id: int | None = None, layout_ids: List[int] | None = None):
    async with _get_lock(context, '_layouts_lock'):
        bus = context.get('bus')
        user_id = context.get('user_id')  # This might be None for unauthenticated requests

        async with bus.uow.get_uow(user_id=user_id) as uow:

            layouts_map = context.get('layouts_map', dict())
            arrangement_roots = context.get('arrangement_roots', list())
            if layout_ids is None:
                if not layouts_map:
                    async for arrangement in uow.repositories.arrangements.get_all(location_id=location_id):
                        layouts_map.update(arrangement.to_output_map())
                        arrangement_roots.append(arrangement.root.id)
                else:
                    return # if we already have layouts loaded just leave it

            else:
                for layout_id in layout_ids:
                    if layout_id in layouts_map:
                        continue # already loaded
                    else:
                        arrangement = await uow.repositories.arrangements.get(layout_id=layout_id)
                        if arrangement is not None:
                            layouts_map.update(arrangement.to_output_map())
                            arrangement_root = arrangement.root
                            if not arrangement_root in arrangement_roots:
                                arrangement_roots.append(arrangement_root)

            context['layouts_map'] = layouts_map
            context['arrangement_roots'] = arrangement_roots

async def update_units_map(context, location_id: int | None = None, unit_id: int | None = None):
    async with _get_lock(context, '_units_lock'):
        bus = context.get('bus')
        user_id = context.get('user_id')  # This might be None for unauthenticated requests

        async with bus.uow.get_uow(user_id=user_id) as uow:

            units_map = context.get('units_map', dict())
            block_roots = context.get('block_roots', list())

            if unit_id is None and not units_map:
                async for block in uow.repositories.blocks.get_all(location_id=location_id):
                    units_map.update(block.to_output_map())
                    block_roots.append(block.root.id)

            if unit_id is not None and not unit_id in units_map:
                block = await uow.repositories.blocks.get(unit_id=unit_id)
                if block is not None:
                    units_map.update(block.to_output_map())
                    block_root = block.root
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
    async with _get_lock(context, '_programs_lock'):
        bus = context.get('bus')
        user_id = context.get('user_id')  # This might be None for unauthenticated requests

        async with bus.uow.get_uow(user_id=user_id) as uow:
            programs_map = context.get('programs_map', dict())
            if program_id is None and not programs_map:
                async for program in uow.repositories.programs.get_all():
                    programs_map.update(program.to_output_map())
            elif program_id is not None and not program_id in programs_map:
                program = await uow.repositories.programs.get(program_id=program_id)
                programs_map.update(program.to_output_map())
            if trial_id is not None:
                for program_id, program in programs_map.values():
                    if trial_id in program.trials:
                        break
                else:
                    program = await uow.repositories.programs.get(trial_id=trial_id)
                    programs_map.update(program.to_output_map())
            if study_id is not None:
                for program_id, program in programs_map.values():
                    for trial_id, trial in program.trials.items():
                        if study_id in trial.studies:
                            break
                    else:
                        program = await uow.repositories.programs.get(study_id=study_id)
                        programs_map.update(program.to_output_map())
                        break

            context['programs_map'] = programs_map


async def update_germplasm_map(
        context,
        entry_ids: List[int] = None,
        names: List[str] = None
):
    async with _get_lock(context, '_germplasm_lock'):
        bus = context.get('bus')
        user_id = context.get('user_id')  # This might be None for unauthenticated requests

        async with bus.uow.get_uow(user_id=user_id) as uow:
            if not 'germplasm_map' in context:
                context['germplasm_map'] = dict()

            entries_to_update = [
                entry_id for entry_id in entry_ids or [] if entry_id not in context['germplasm_map']
            ]
            async for entry in uow.germplasm.get_entries(
                entry_ids=entries_to_update,
                names=names,
                as_output=True
            ):
                context['germplasm_map'][entry.id] = entry