from breedgraph.domain.model.regions import Region, LocationInput, LocationStored

from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory, AbstractUnitHolder

from breedgraph.custom_exceptions import IdentityExistsError

from tests.utilities.inputs import LoremTextGenerator

from typing import Dict

class RegionBuilder:
    text_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory, state_store: AbstractStateStore):
        self.uow_factory = uow_factory
        self.state_store = state_store

    async def region_from_country(self, uow: AbstractUnitHolder) -> Region:
        region = None
        count = 0
        async for country in self.state_store.get_countries():
            count += 1
            if isinstance(country, LocationStored):
                pass
            else:
                try:
                    region = await uow.repositories.regions.create(country)
                    break
                except IdentityExistsError:
                    pass
        if count == 0:
            raise ValueError("No countries were found in read model to create a test region")
        elif region is None:
            raise ValueError("All stored countries are already created!")
        return region

    async def region(
            self,
            user_id: int,
            ontology_location_state:int,
            ontology_location_field:int,
            ontology_location_lab: int
    ) -> Dict[str, int]:

        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            region = await self.region_from_country(uow)
            state_temp_id = region.add_location(
                LocationInput(name=self.text_generator.new_text(10), type=ontology_location_state),
                parent_id=region.get_root_id()
            )
            region.add_location(
                LocationInput(name=self.text_generator.new_text(10), type=ontology_location_field),
                parent_id=state_temp_id
            )
            region.add_location(
                LocationInput(name=self.text_generator.new_text(10), type=ontology_location_lab),
                parent_id=state_temp_id
            )
            await uow.commit()

        country = region.root
        state = next(region.yield_locations_by_type(ontology_location_state))
        field = next(region.yield_locations_by_type(ontology_location_field))
        lab = next(region.yield_locations_by_type(ontology_location_lab))
        return {
            'location_country_id': country.id,
            'location_country_name': country.name,
            'location_state_id': state.id,
            'location_state_name': state.name,
            'location_field_id': field.id,
            'location_field_name': field.name,
            'location_lab_id': lab.id,
            'location_lab_name': lab.name
        }


