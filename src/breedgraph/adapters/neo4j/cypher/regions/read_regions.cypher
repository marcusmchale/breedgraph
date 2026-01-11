MATCH (root: Location) WHERE NOT (root)<-[:INCLUDES_LOCATION]-(:Location)
OPTIONAL MATCH (root)-[:INCLUDES_LOCATION*]->(child:Location)
WITH root, coalesce(collect(child), []) AS children
WITH root.id as root_id, root + children AS locations
UNWIND locations as location

OPTIONAL CALL (location) {
  MATCH (location)<-[coord_of:COORDINATE_OF]-(coordinate:Coordinate)
  WITH coordinate, coord_of
  ORDER BY coord_of.position
  RETURN collect(coordinate {.*}) as coordinates
}

OPTIONAL MATCH (location)-[:OF_LOCATION_TYPE]->(type:LocationType)
OPTIONAL MATCH (parent:Location)-[:INCLUDES_LOCATION]->(location)
WITH root_id, collect(
  location {
    .*,
    coordinates: coalesce(coordinates, []),
    type: type.id,
    parent_id: parent.id
  }
) as locations
return locations as region
