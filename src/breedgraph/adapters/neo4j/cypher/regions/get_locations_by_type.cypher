MATCH
  (location: Location)-[:OF_LOCATION_TYPE]->(type:LocationType {id: $location_type})
RETURN location {
  .*,
  type: [(location)-[:OF_LOCATION_TYPE]->(type:LocationType) | type.id][0],
  coordinates: [(location)<-[:COORDINATE_OF]-(coordinate:Coordinate) | coordinate {.*}],
  parent: [(parent:Location)-[:INCLUDES_LOCATION]->(location) | parent.id][0],
  children: [(location)-[:INCLUDES_LOCATION]->(child) | child.id]
}