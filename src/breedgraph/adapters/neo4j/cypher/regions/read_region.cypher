MATCH
  (captured: Location {id: $location_id})
OPTIONAL MATCH (captured)-[:INCLUDES_LOCATION*]-(extended:Location)

WITH captured, coalesce(collect(extended), []) AS locations
WITH captured + locations AS region
UNWIND region AS location
RETURN location {
  .*,
  type: [(location)-[:OF_LOCATION_TYPE]->(type:LocationType) | type.id][0],
  coordinates: [(location)<-[:COORDINATE_OF]-(coordinate:Coordinate) | coordinate {.*}],
  parent_id: [(parent:Layout)-[:INCLUDES_LAYOUT]->(layout) | parent.id][0]
}
