import asyncio
from contextlib import AsyncExitStack

from typing import Iterable, List

import logging

from breedgraph.domain.model import Version

from breedgraph.service_layer.queries.read_models import OntologyEntryOutput, OntologyViewMode
from breedgraph.domain.model.regions import LocationOutput
from breedgraph.domain.model.arrangements import LayoutOutput
from breedgraph.domain.model.blocks import UnitOutput

logger = logging.getLogger(__name__)

# Helper functions to get or create locks for each map type to prevent concurrent updates

def _get_lock(context, lock_name: str):
    """Get or create a lock for a specific map in this context"""
    if lock_name not in context:
        context[lock_name] = asyncio.Lock()
    return context[lock_name]


def get_context_lock(context):
    """The lock to hold while using the request's shared views holder"""
    return _get_lock(context, '_views_lock')


async def get_context_views(context):
    """
    One views holder for the whole request, opened on first use and closed with the request's exit stack
    (see graphql_endpoint), so per-field resolvers don't each open a session and load the user's access teams.
    The holder shares one database session, which cannot run transactions concurrently: call this, and use
    the views it returns, while holding the context's '_views_lock'.
    """
    if 'views' not in context:
        if '_exit_stack' not in context:
            context['_exit_stack'] = AsyncExitStack()
        bus = context.get('bus')
        context['views'] = await context['_exit_stack'].enter_async_context(
            bus.views_factory.get_views(user_id=context.get('user_id'))
        )
    return context['views']


async def close_context(context):
    """Release what the loaders opened for this request"""
    stack = context.get('_exit_stack') if context else None
    if stack is not None:
        await stack.aclose()


async def load_entries_to_ontology_map(
        context,
        entries: Iterable[OntologyEntryOutput],
        version_id: int|None,
        view: OntologyViewMode
):
    if version_id is None:
        for entry in entries:
            version_id = entry.version.packed_version
            break
        else:
            raise ValueError("No entries provided")

    async with _get_lock(context, '_ontology_lock'):
        if not 'ontology_map' in context:
            context['ontology_map'] = dict()

        if not 'ontology_view' in context:
            context['ontology_view'] = {
                'version_id': version_id,
                'view': view
            }
        else:
            if context['ontology_view']['version_id'] != version_id:
                raise ValueError("Context version changed")
            if context['ontology_view']['view'] != view:
                raise ValueError("Context view changed")

        ontology_map = context.get('ontology_map')
        ontology_map.update({entry.id: entry for entry in entries})

async def update_ontology_map(
        context,
        entry_ids: Iterable[int],
        version_id: int|None = None,
        view: OntologyViewMode | None = None
):
    async with _get_lock(context, '_ontology_lock'):
        if not 'ontology_map' in context:
            context['ontology_map'] = dict()
        ontology_map = context.get('ontology_map')

        bus = context.get('bus')
        entry_ids = set(entry_ids or [])
        entries_to_update = [i for i in entry_ids - ontology_map.keys()]
        if entries_to_update:
            async with bus.views_factory.get_views() as views:
                if not 'ontology_view' in context:
                    view = view or OntologyViewMode.PUBLISHED
                    version = Version.from_packed(version_id) if version_id else await views.ontology.get_current_version()
                    context['ontology_view'] = {
                        'version_id': version.packed_version,
                        'view': view
                    }
                else:
                    context_version_id = context['ontology_view']['version_id']
                    if version_id is not None and context_version_id != version_id:
                        raise ValueError("Ontology context version changed in the middle of resolving a query")

                    version = Version.from_packed(context_version_id)

                    context_view = context['ontology_view']['view']
                    if view is not None and view != context_view:
                        raise ValueError("Ontology context view changed in the middle of resolving a query")
                    view = context_view
                entries = await views.ontology.get_entries(
                    entry_ids=entries_to_update,
                    version=version,
                    view=view
                )
                ontology_map.update({entry.id: entry for entry in entries})

async def update_teams_map(context, team_ids: Iterable[int] | None = None):
    async with _get_lock(context, '_teams_lock'):
        bus = context.get('bus')
        user_id = context.get('user_id')  # This might be None for unauthenticated requests
        teams_map = context.get('teams_map', dict())
        organisation_roots = context.get('organisation_roots', list())
        logger.debug('Updating teams map for user ' + str(user_id) + ' with team ids: ' + str(team_ids) + '')
        async with bus.uow_factory.get_uow(user_id=user_id) as uow:
            # if called with teams = None, retrieve all organisations
            # organisation_roots holds root ids, each once, in the order first loaded
            if team_ids is None:
                async for org in uow.repositories.organisations.get_all():
                    org = org.redacted(user_id)
                    teams_map.update(org.to_output_map())
                    if org.root.id not in organisation_roots:
                        organisation_roots.append(org.root.id)
            else:
                team_ids = set(team_ids)
                unmapped = team_ids - set(teams_map.keys())
                if unmapped:
                    n = 0
                    async for org in uow.repositories.organisations.get_all(team_ids=team_ids):
                        if org is not None:
                            org = org.redacted(user_id)
                            n+=1
                            logger.debug(f"Updating teams map with {org.root.id} for {user_id} at {n}")
                            logger.debug(f"Teams map: {teams_map}")
                            teams_map.update(org.to_output_map())
                            logger.debug(f"Teams map after update: {teams_map}")
                            if org.root.id not in organisation_roots:
                                organisation_roots.append(org.root.id)

            context['teams_map'] = teams_map
            context['organisation_roots'] = organisation_roots

async def update_users_map(context, user_ids: Iterable[int] | None = None):
    """
    Load the users the agent may see into the request's users map. Users that cannot be shown are remembered as
    such, so resolving many write stamps by the same hidden user reads it once rather than once per stamp.
    """
    async with (_get_lock(context, '_users_lock')):
        agent_id = context.get('user_id')  # This might be None for unauthenticated requests
        users_map = context.setdefault('users_map', dict())
        unavailable = context.setdefault('_users_unavailable', set())

        user_ids = {user_id for user_id in user_ids or [] if user_id is not None}
        unmapped = list(user_ids - users_map.keys() - unavailable)
        if not unmapped:
            return

        bus = context.get('bus')
        async with bus.views_factory.get_views(user_id=agent_id) as views:
            for user in await views.accounts.get_users_for_admin(user_ids=unmapped):
                users_map[user.id] = user

            if agent_id in unmapped and not agent_id in users_map:
                users_map[agent_id] = await views.accounts.get_user()

        unavailable.update(user_id for user_id in unmapped if user_id not in users_map)

async def update_locations_map(context, location_ids: Iterable[int] | None = None) -> List[LocationOutput]:
    """
    Load locations into the request's locations map through the regions view, by id, or, with no ids, the root of
    every region the user can read a location in, which are returned. Hidden locations asked for come back as the
    view's placeholders; ids of locations that do not exist are not mapped.
    """
    async with _get_lock(context, '_views_lock'):
        locations_map = context.setdefault('locations_map', dict())
        views = await get_context_views(context)
        if location_ids is None:
            roots = await views.regions.get_regions()
            locations_map.update({root.id: root for root in roots})
            return roots

        location_ids = list(location_ids)
        unmapped = [location_id for location_id in dict.fromkeys(location_ids) if location_id is not None and location_id not in locations_map]
        if unmapped:
            locations_map.update(await views.regions.get_locations(unmapped))
        return [locations_map[location_id] for location_id in location_ids if location_id in locations_map]

async def update_layouts_map(context, location_id: int | None = None, layout_ids: Iterable[int] | None = None) -> List[LayoutOutput]:
    """
    Load layouts into the request's layouts map through the arrangements view, by id, or the roots of the
    arrangements at a location the user can read a layout in, which are returned. Hidden layouts asked for come back
    as the view's placeholders; ids of layouts that do not exist are not mapped.
    """
    async with _get_lock(context, '_views_lock'):
        layouts_map = context.setdefault('layouts_map', dict())
        views = await get_context_views(context)
        if location_id is not None:
            roots = await views.arrangements.get_arrangements(location_id)
            layouts_map.update({root.id: root for root in roots})
            return roots

        layout_ids = list(layout_ids or [])
        unmapped = [layout_id for layout_id in dict.fromkeys(layout_ids) if layout_id is not None and layout_id not in layouts_map]
        if unmapped:
            layouts_map.update(await views.arrangements.get_layouts(unmapped))
        return [layouts_map[layout_id] for layout_id in layout_ids if layout_id in layouts_map]

async def update_units_map(context, location_ids: Iterable[int] | None = None, unit_ids: Iterable[int] | None = None):
    """
    Load units into the request's units map through the units view, by id or as the block roots at locations.
    Units are read individually, not by loading their whole block, so the cost follows the ids requested.
    Callers that resolve many objects should pass all their ids in one call (see Dataset.records).
    """
    async with _get_lock(context, '_views_lock'):
        units_map = context.setdefault('units_map', dict())
        block_roots = context.setdefault('block_roots', list())
        views = await get_context_views(context)

        if location_ids is not None:
            for unit in await views.units.get_block_roots(location_ids=location_ids):
                units_map[unit.id] = unit
                if unit.id not in block_roots:
                    block_roots.append(unit.id)

        if unit_ids is not None:
            unmapped = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None and unit_id not in units_map]
            if unmapped:
                units_map.update(await views.units.get_units(unit_ids=unmapped))

async def update_unit_names_map(context, unit_ids: Iterable[int]):
    """
    Units as id, name and germplasm only, for crediting records: the full units map is not consulted or filled,
    so crediting 25,000 records does not read their positions, edges and neighbours.
    """
    async with _get_lock(context, '_views_lock'):
        names_map = context.setdefault('unit_names_map', dict())
        unmapped = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None and unit_id not in names_map]
        if unmapped:
            views = await get_context_views(context)
            names_map.update(await views.units.get_unit_names(unit_ids=unmapped))


async def update_germplasm_map(
        context,
        entry_ids: Iterable[int]|None = None
):
    async with _get_lock(context, '_views_lock'):
        germplasm_map = context.setdefault('germplasm_map', dict())
        if entry_ids is None:
            # everything, once per request
            if context.get('_germplasm_all_loaded'):
                return
            context['_germplasm_all_loaded'] = True
            to_load = None
        else:
            to_load = [
                entry_id for entry_id in dict.fromkeys(entry_ids)
                if entry_id is not None and entry_id not in germplasm_map
            ]
            if not to_load:
                return
        views = await get_context_views(context)
        for entry in await views.germplasm.get_entries(entry_ids=to_load):
            germplasm_map[entry.id] = entry

async def update_reference_map(
        context,
        reference_ids: Iterable[int]|None = None
):
    if not 'reference_map' in context:
        context['reference_map'] = dict()
    if not reference_ids:
        return

    # through the references view: a reference the user cannot read is a placeholder (see docs/read-access.md)
    async with _get_lock(context, '_reference_lock'):
        references_to_update = [
            reference_id for reference_id in reference_ids if reference_id not in context['reference_map']
        ]
        if references_to_update:
            async with get_context_lock(context):
                views = await get_context_views(context)
                for reference in await views.references.get_references(references_to_update):
                    context['reference_map'][reference.id] = reference


async def update_people_map(context, person_ids: Iterable[int] | None = None):
    """
    Load Persons by id into context['people_map'], for resolving references to Persons, through the people view:
    a Person the user cannot read is a placeholder, its id with no name (see docs/read-access.md)
    """
    async with _get_lock(context, '_people_lock'):
        people_map = context.setdefault('people_map', dict())
        unmapped = set(person_ids or []) - set(people_map.keys())
        if not unmapped:
            return
        async with get_context_lock(context):
            views = await get_context_views(context)
            for person in await views.people.get_people(sorted(unmapped)):
                people_map[person.id] = person

async def resolve_user_person(context, user_id: int | None):
    """
    The Person linked to an account, for attributing what the account did: a placeholder if the agent cannot read it,
    None if the account has no Person. Accounts are shown only to their owner and admins of their teams; their Persons
    follow the read policy (see docs/person.md).
    """
    if user_id is None:
        return None
    async with _get_lock(context, '_user_people_lock'):
        user_people = context.setdefault('user_people_map', dict())
        if user_id not in user_people:
            async with get_context_lock(context):
                views = await get_context_views(context)
                # the Persons of the accounts asked for together, should the caller have gathered them
                pending = set(context.pop('_user_people_pending', set())) | {user_id}
                found = await views.people.get_people_by_users(sorted(pending - user_people.keys()))
            for pending_id in pending:
                user_people.setdefault(pending_id, found.get(pending_id))
            people_map = context.setdefault('people_map', dict())
            for person in found.values():
                people_map.setdefault(person.id, person)
        return user_people[user_id]


def prepare_user_people(context, user_ids: Iterable[int]) -> None:
    """Note accounts whose Persons will be asked for, so the first resolve_user_person reads them all at once"""
    pending = context.setdefault('_user_people_pending', set())
    pending.update(user_id for user_id in user_ids if user_id is not None)


async def resolve_people(context, person_ids: Iterable[int] | None) -> list:
    """Resolve references to Persons, in order, placeholders for those the user cannot read"""
    person_ids = list(person_ids or [])
    await update_people_map(context, person_ids=person_ids)
    people_map = context.get('people_map', {})
    return [people_map[person_id] for person_id in person_ids if person_id in people_map]


async def team_references(context, team_ids) -> list[dict]:
    """
    References to these teams as the user sees them, for GraphQL's TeamReference: the team, or for a team hidden from
    the user, the nearest team they can see that includes it, its organisation's root at the furthest, marked as a
    stand-in (see docs/read-access.md, rule 7). In order, each team once as itself and once as a stand-in at most.
    """
    team_ids = list(team_ids or [])
    await update_teams_map(context=context, team_ids=team_ids)
    teams_map = context.get('teams_map', {})
    references = {}
    for team_id in team_ids:
        team = teams_map.get(team_id)
        if team is not None:
            stand_in = team.id != team_id
            references.setdefault((team.id, stand_in), {'team': team, 'stand_in': stand_in})
    return list(references.values())
