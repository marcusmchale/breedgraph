MATCH
  (location: Location)-[:OF_LOCATION_TYPE]->(type:LocationType {id: $type})
RETURN location {
  .*,
  type: [(location)-[:OF_LOCATION_TYPE]->(type:LocationType) | type.id][0],
  coordinates: [(location)<-[:COORDINATE_OF]-(coordinate:Coordinate) | coordinate {.*}]
}