from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import visible_members, tree_links

# Locations as the user may see them, each as the repository's output map gives it (location tree, parent and children ids),
# with the hidden locations of a location tree skipped: a parent is the nearest readable ancestor or the location tree's root, and
# children are the nearest readable descendants. A location the user can read is returned in full. A hidden location tree
# root is returned as a placeholder, its id and a REDACTED name, keeping its readable descendants as children, when it
# was asked for directly or holds locations the user can read. Any other hidden location asked for by id is returned
# as a bare placeholder; otherwise hidden locations are left out.

LOCATION = ControlledModelLabel.LOCATION
EDGE = 'INCLUDES_LOCATION'


def _with_root(location: str = 'location') -> str:
    """Group locations by the root of their location tree, with the ids in it the user can read, as root and visible_ids"""
    return f"""
        MATCH (root:Location)-[:{EDGE}*0..]->({location})
        WHERE NOT (:Location)-[:{EDGE}]->(root)
        WITH root, collect(DISTINCT {location}) AS locations
        {visible_members('root', LOCATION, EDGE, 'visible_ids')}
        UNWIND locations AS {location}
    """


def _location(location: str = 'location') -> str:
    links = tree_links(location, 'root', LOCATION, EDGE, 'visible_ids')
    return f"""CASE
          WHEN {location}.id IN visible_ids THEN {location} {{
            .*,
            type: [({location})-[:OF_LOCATION_TYPE]->(type:LocationType) | type.id][0],
            coordinates: COLLECT {{
              MATCH ({location})<-[coord_of:COORDINATE_OF]-(coordinate:Coordinate)
              WITH coordinate, coord_of ORDER BY coord_of.position
              RETURN coordinate {{.*}}
            }},
            root: root.id,
            parent: {links['parent']},
            children: {links['children']}
          }}
          WHEN {location} = root THEN {location} {{ .id, name: 'REDACTED', root: root.id, children: {links['children']} }}
          ELSE {location} {{ .id, name: 'REDACTED' }}
        END"""


def read_locations():
    """The locations with ids $location_ids, a placeholder for those the user cannot read"""
    return f"""
        MATCH (location:Location) WHERE location.id IN $location_ids
        {_with_root()}
        RETURN {_location()} AS location
    """


def read_location_trees():
    """The root of every location tree the user can read a location in"""
    return f"""
        MATCH (location:Location) WHERE NOT (:Location)-[:{EDGE}]->(location)
        {_with_root()}
        WITH root, visible_ids, location WHERE size(visible_ids) > 0
        RETURN {_location()} AS location
        ORDER BY location.id
    """


def read_locations_by_type():
    """The locations of type $location_type that the user can read"""
    return f"""
        MATCH (location:Location)-[:OF_LOCATION_TYPE]->(:LocationType {{id: $location_type}})
        {_with_root()}
        WITH root, visible_ids, location WHERE location.id IN visible_ids
        RETURN {_location()} AS location
        ORDER BY location.id
    """
