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
// Create coordinates
CALL {
  WITH location
  MATCH (location)<-[coordinate_of:COORDINATE_OF]-(coordinate: Coordinate)
  DELETE coordinate_of, coordinate
  WITH DISTINCT location
  UNWIND $coordinates AS c
  CREATE (location)<-[:COORDINATE_OF]-(coordinate:Coordinate {
    sequence:    c.sequence,
    latitude:    c.latitude,
    longitude:   c.longitude,
    altitude:    c.altitude,
    uncertainty: c.uncertainty,
    description: c.description
  })
  RETURN collect(coordinate {.*}) as coordinates
}
RETURN
  location {
    .*,
    coordinates: coordinates,
    type: type
  }
