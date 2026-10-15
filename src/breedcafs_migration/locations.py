"""
Locations for the BreedCAFS country/region/farm/field hierarchy (README.md §3, 1_1_Extract_Locations.md).

Each BreedCAFS country is the root location of a BreedGraph region, found by its ISO 3166-1 alpha-3 code,
or created, publicly released as countries are. Under it, the regions, farms and fields of field_farm_region_country.csv
are matched by name and type under their parent, or created, `PRIVATE` and controlled by the migration team.
Fields are given their coordinates from field_lat_long.csv when created.
The locations given for samples by the "Location (text)" input (sample_positions.csv) are created as in SAMPLE_LOCATIONS.

Running this again matches the locations created before.
Writes location_ids.csv, mapping each BreedCAFS field to its location,
and sample_location_ids.csv, mapping each sample location value to its location.

Countries are a read model in the API's state store, refreshed at the end of this phase (as on every run,
in case an earlier run stopped before it), so the API sees the countries as stored.
"""
import csv
from dataclasses import dataclass, field

from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.adapters.redis.read_models import RedisReadModels
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.regions import Region, LocationInput, GeoCoordinate

from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

import logging
logger = logging.getLogger(__name__)

# BreedCAFS country name -> ISO 3166-1 alpha-3 code and the name used for countries (UN M49, src/data/country_codes.csv)
COUNTRIES = {
    "Cameroon": ("CMR", "Cameroon"),
    "Costa Rica": ("CRI", "Costa Rica"),
    "Denmark": ("DNK", "Denmark"),
    "France": ("FRA", "France"),
    "French Guiana": ("GUF", "French Guiana"),
    "Nicaragua": ("NIC", "Nicaragua"),
    "Vietnam": ("VNM", "Viet Nam"),
}
COORDINATE_DESCRIPTION = "Field location from BreedCAFS"

# "Location (text)" value -> country, and the path of (name, location type) under it
SAMPLE_LOCATIONS = {
    "Montpellier/ IRD": ("France", [("IRD Montpellier", "Research Center")]),
}

# A location path under a country: (name, location type name, other location details)
Path = list[tuple[str, str, dict]]


@dataclass
class LocationIds:
    # BreedCAFS country name -> location id of the country
    countries: dict[str, int] = field(default_factory=dict)
    # BreedCAFS field uid -> location id of the field
    fields: dict[str, int] = field(default_factory=dict)
    # "Location (text)" value -> location id
    sample_locations: dict[str, int] = field(default_factory=dict)
    countries_created: set[str] = field(default_factory=set)
    created: int = 0


def clean(value: str) -> str:
    """Values in the exported CSVs are wrapped in extra quotes"""
    return (value or '').strip().strip('"').strip()


def read_fields() -> list[dict[str, str]]:
    with open(BREEDCAFS_DATA_DIR / 'field_farm_region_country.csv', encoding='utf-8-sig') as f:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(f)]


def read_coordinates() -> dict[str, GeoCoordinate]:
    with open(BREEDCAFS_DATA_DIR / 'field_lat_long.csv', encoding='utf-8-sig') as f:
        return {
            clean(row['field_uid']): GeoCoordinate(
                latitude=float(clean(row['lat'])),
                longitude=float(clean(row['long'])),
                altitude=None,
                uncertainty=None,
                description=COORDINATE_DESCRIPTION
            )
            for row in csv.DictReader(f)
        }


def read_sample_locations() -> set[str]:
    with open(BREEDCAFS_DATA_DIR / 'sample_positions.csv', encoding='utf-8-sig') as f:
        return {clean(row['location']) for row in csv.DictReader(f)}


def find_child(region: Region, parent_id: int, name: str, type_id: int) -> int | None:
    for child_id in region.get_children_ids(parent_id):
        child = region.get_location(child_id)
        if child.type == type_id and child.name.casefold() == name.casefold():
            return child_id
    return None


class LocationPreparation:
    def __init__(self, uow_factory: Neo4jUnitOfWorkFactory, context: MigrationContext, location_types: dict[str, int]):
        self.uow_factory = uow_factory
        self.context = context
        self.location_types = location_types
        self.ids = LocationIds()

    async def country(self, name: str) -> int:
        code, country_name = COUNTRIES[name]
        async with self.uow_factory.get_uow(
                user_id=self.context.user_id, write_team=self.context.team_id, release=ReadRelease.PUBLIC
        ) as uow:
            region = await uow.repositories.regions.get(code=code)
            if region is None:
                region = await uow.repositories.regions.create(
                    LocationInput(name=country_name, code=code, type=self.location_types["Country"])
                )
                await uow.commit()
                self.ids.countries_created.add(name)
                self.ids.created += 1
            return region.get_root_id()

    def child(self, region: Region, parent_id: int, name: str, type_name: str, **details) -> int:
        type_id = self.location_types[type_name]
        child_id = find_child(region, parent_id, name, type_id)
        if child_id is None:
            child_id = region.add_location(LocationInput(name=name, type=type_id, **details), parent_id=parent_id)
            self.ids.created += 1
        return child_id

    async def paths(self, country: str, paths: list[Path]) -> list[int]:
        """The location at the end of each path under the country, creating what is missing. Returns their ids."""
        country_id = self.ids.countries[country]
        async with self.uow_factory.get_uow(user_id=self.context.user_id, write_team=self.context.team_id) as uow:
            region = await uow.repositories.regions.get(location_id=country_id)
            for path in paths:
                parent_id = country_id
                for name, type_name, details in path:
                    parent_id = self.child(region, parent_id, name, type_name, **details)
            await uow.commit()

        # Read again for the ids of locations created above
        async with self.uow_factory.get_uow(user_id=self.context.user_id) as uow:
            region = await uow.repositories.regions.get(location_id=country_id)
            ids = []
            for path in paths:
                location_id = country_id
                for name, type_name, _ in path:
                    location_id = find_child(region, location_id, name, self.location_types[type_name])
                ids.append(location_id)
            return ids

    async def prepare(self) -> LocationIds:
        fields = read_fields()
        coordinates = read_coordinates()
        sample_locations = sorted(read_sample_locations())
        unmapped = [location for location in sample_locations if location not in SAMPLE_LOCATIONS]
        if unmapped:
            raise ValueError(f"No location is given in SAMPLE_LOCATIONS for these sample locations: {unmapped}")

        # BreedCAFS key -> country and path, for fields and for sample locations
        paths: dict[tuple[str, str], tuple[str, Path]] = {}
        for row in fields:
            coordinate = coordinates.get(row['field_uid'])
            paths[('field', row['field_uid'])] = (row['country'], [
                (row['region'], "Region", {}),
                (row['farm'], "Farm", {}),
                (row['field'], "Field", {'coordinates': [coordinate] if coordinate else []}),
            ])
        for location in sample_locations:
            country, path = SAMPLE_LOCATIONS[location]
            paths[('sample', location)] = (country, [(name, type_name, {}) for name, type_name in path])

        countries = sorted({country for country, _ in paths.values()})
        unknown = [country for country in countries if country not in COUNTRIES]
        if unknown:
            raise ValueError(f"No ISO 3166 code is given for these countries: {unknown}")
        for country in countries:
            self.ids.countries[country] = await self.country(country)
            keys = [key for key, (key_country, _) in paths.items() if key_country == country]
            for (kind, key), location_id in zip(keys, await self.paths(country, [paths[k][1] for k in keys])):
                (self.ids.fields if kind == 'field' else self.ids.sample_locations)[key] = location_id
        return self.ids


async def prepare_breedcafs_locations(
        uow_factory: Neo4jUnitOfWorkFactory,
        context: MigrationContext,
        location_types: dict[str, int]
) -> LocationIds:
    ids = await LocationPreparation(uow_factory, context, location_types).prepare()
    logger.info(f"Prepared locations: {ids.created} created, {len(ids.fields)} fields mapped")
    if ids.countries_created:
        logger.info(f"Countries created: {sorted(ids.countries_created)}")
    write_mappings(ids)
    read_models = await RedisReadModels.create(driver=uow_factory.driver)
    try:
        await read_models.refresh(['countries'])
    finally:
        await read_models.close()
    return ids


def write_mappings(ids: LocationIds) -> None:
    with open(BREEDCAFS_DATA_DIR / 'location_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['field_uid', 'location_id'])
        for field_uid, location_id in sorted(ids.fields.items(), key=lambda item: int(item[0])):
            writer.writerow([field_uid, location_id])
    with open(BREEDCAFS_DATA_DIR / 'sample_location_ids.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['location', 'location_id'])
        for location, location_id in sorted(ids.sample_locations.items()):
            writer.writerow([location, location_id])
