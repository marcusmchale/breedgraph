MATCH (location: Location {id:$id})
SET
  location.name = $name,
  location.synonyms = $synonyms,
  location.description = $description,
  location.code = $code,
  location.address = $address
WITH
  location
// Link type
CALL {
  WITH location
  MATCH (location)-[of_type:OF_LOCATION_TYPE]->(type:LocationType)
  WHERE NOT type.id = $type
  DELETE of_type
  WITH DISTINCT location
  MATCH (type:LocationType {id: $type})
  MERGE (location)-[of_type:OF_LOCATION_TYPE]->(type)
  ON CREATE SET of_type.time = datetime.transaction()
  RETURN collect(type.id)[0] as type
}
// Remove existing coordinates
OPTIONAL CALL (location) {
  MATCH (location)<-[coordinate_of:COORDINATE_OF]-(coordinate: Coordinate)
  DETACH DELETE coordinate
}
// Create coordinates
CALL (location) {
  UNWIND range(0, size($coordinates)-1) as i
  CREATE (location)<-[coordinate_of:COORDINATE_OF {position: i}]-(coordinate:Coordinate {
    sequence:    $coordinates[i].sequence,
    latitude:    $coordinates[i].latitude,
    longitude:   $coordinates[i].longitude,
    altitude:    $coordinates[i].altitude,
    uncertainty: $coordinates[i].uncertainty,
    description: $coordinates[i].description
  })
  WITH coordinate ORDER BY coordinate_of.position
  RETURN collect(coordinate {.*}) as coordinates
}
RETURN
  location {
    .*,
    coordinates: coordinates,
    type: type
  }
