MATCH
  (location: Location)-[:OF_LOCATION_TYPE]->(type:LocationType {id: $location_type})
OPTIONAL MATCH (location)-[:OF_LOCATION_TYPE]->(type:LocationType)
OPTIONAL MATCH (parent:Location)-[:INCLUDES_LOCATION]->(location)

OPTIONAL CALL (location) {
  MATCH (location)<-[coord_of:COORDINATE_OF]-(coordinate:Coordinate)
  WITH coordinate, coord_of
  ORDER BY coord_of.position
  RETURN collect(coordinate {.*}) as coordinates
}

OPTIONAL CALL (location) {
  MATCH (location)-[:INCLUDES_LOCATION]->(child: Location)
  RETURN collect(child.id) as children
}

RETURN location {
  .*,
  type: type.id,
  coordinates: coalesce(coordinates, []),
  parent: parent.id,
  children: coalesce(children, [])
}