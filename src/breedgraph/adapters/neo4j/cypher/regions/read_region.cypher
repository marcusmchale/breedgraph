MATCH
  (captured: Location {id: $location_id})
OPTIONAL MATCH (captured)-[:INCLUDES_LOCATION*]-(extended:Location)

WITH captured, coalesce(collect(extended), []) AS locations
WITH captured + locations AS region
UNWIND region AS location
OPTIONAL CALL (location) {
  MATCH (location)<-[coord_of:COORDINATE_OF]-(coordinate:Coordinate)
  WITH coordinate, coord_of
  ORDER BY coord_of.position
  RETURN collect(coordinate {.*}) as coordinates
}
RETURN location {
  .*,
  type: [(location)-[:OF_LOCATION_TYPE]->(type:LocationType) | type.id][0],
  coordinates: coalesce(coordinates, []),
  parent_id: [(parent:Location)-[:INCLUDES_LOCATION]->(location) | parent.id][0]
}
