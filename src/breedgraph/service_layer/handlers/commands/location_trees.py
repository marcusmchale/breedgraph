from breedgraph.domain import commands
from breedgraph.domain.events.location_trees import CountryAdded, LocationPlaced, CountryRemoved
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.ontology import OntologyEntryLabel
from breedgraph.domain.model.location_trees import LocationTree, LocationInput, LocationStored, LocationOutput, GeoCoordinate

from breedgraph.adapters.redis.state_store import RedisStateStore
from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory, AbstractReadModels

from breedgraph.custom_exceptions import IdentityExistsError

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


def _points(coordinates) -> list:
    return [(coordinate['latitude'], coordinate['longitude']) for coordinate in coordinates or []]


@handlers.command_handler()
async def create_location(
        cmd: commands.location_trees.CreateLocation,
        uow_factory: AbstractUnitOfWorkFactory,
        state_store: RedisStateStore,
        read_models: AbstractReadModels
):
    location_input = LocationInput(
        name = cmd.name,
        fullname = cmd.fullname,
        type = cmd.type_id,
        code = cmd.code,
        address = cmd.address,
        coordinates = [GeoCoordinate(**coord.model_dump()) for coord in cmd.coordinates or []]
    )

    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        await uow.ontology.require_entries([cmd.type_id], label=OntologyEntryLabel.LOCATION_TYPE)
        if cmd.parent_id is None:
            # Ensure that root locations (countries) have public read-access
            uow.repositories.location_trees.release = ReadRelease.PUBLIC

        if cmd.parent_id is None:
            country = await state_store.get_country(cmd.code)
            if country is None:
                raise ValueError(
                    "Locations without parent must have 3-letter code of Country according to ISO3166."
                )
            elif isinstance(country, LocationOutput):
                raise IdentityExistsError("This country is already stored")

            location_tree = await uow.repositories.location_trees.create(location_input)
            location_tree.events.append(
                CountryAdded(location_id=location_tree.root.id, code=cmd.code, agent_id=cmd.agent_id)
            )
        else:
            location_tree = await uow.repositories.location_trees.get(location_id=cmd.parent_id)
            existing = set(location_tree.entries)
            location_tree.add_location(location_input, parent_id=cmd.parent_id)
            if location_input.coordinates:
                # stored now, to know its id
                await uow.repositories.location_trees.update_seen()
                [location_id] = set(location_tree.entries) - existing
                location_tree.events.append(LocationPlaced(location_id=location_id, agent_id=cmd.agent_id))

        await uow.commit()

    if cmd.parent_id is None:
        await read_models.refresh(['countries'])


@handlers.command_handler()
async def update_location(
        cmd: commands.location_trees.UpdateLocation,
        uow_factory: AbstractUnitOfWorkFactory,
        read_models: AbstractReadModels
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=cmd.location_id)
        location = location_tree.get_location(cmd.location_id)
        was_root = cmd.location_id == location_tree.root.id

        if cmd.name is not None:
            location.name = cmd.name
        if cmd.given('code'):
            # a country's code is its ISO code, which the countries read model and its removal go by
            if was_root and cmd.given_text('code') is None:
                raise ValueError("A country keeps its code")
            location.code = cmd.given_text('code')
        if cmd.type_id is not None:
            if cmd.type_id != location.type:
                await uow.ontology.require_entries([cmd.type_id], label=OntologyEntryLabel.LOCATION_TYPE)
            location.type = cmd.type_id
        if cmd.given('fullname'):
            location.fullname = cmd.given_text('fullname')
        if cmd.given('description'):
            location.description = cmd.given_text('description')
        if cmd.given('address'):
            location.address = cmd.given_text('address')
        if cmd.coordinates is not None:
            placed = [(coord.latitude, coord.longitude) for coord in cmd.coordinates]
            if placed and not was_root and placed != _points(location.coordinates):
                location_tree.events.append(LocationPlaced(location_id=cmd.location_id, agent_id=cmd.agent_id))
            location.coordinates = [GeoCoordinate(**coord.model_dump()) for coord in cmd.coordinates]
        if cmd.parent_id is not None:
            location_tree.change_source(node_id=cmd.location_id, parent_id=cmd.parent_id)

        await uow.repositories.location_trees.update_seen()
        await uow.commit()

    if was_root:
        # countries are the roots of location trees
        await read_models.refresh(['countries'])

@handlers.command_handler()
async def delete_location(
        cmd: commands.location_trees.DeleteLocation,
        uow_factory: AbstractUnitOfWorkFactory,
        read_models: AbstractReadModels
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        location_tree = await uow.repositories.location_trees.get(location_id=cmd.location_id)
        is_root = cmd.location_id == location_tree.root.id
        if is_root:
            location_tree.events.append(CountryRemoved(code=location_tree.root.code))
            await uow.repositories.location_trees.remove(location_tree)
        else:
            location_tree.remove_location(cmd.location_id)

        await uow.commit()

    if is_root:
        await read_models.refresh(['countries'])
