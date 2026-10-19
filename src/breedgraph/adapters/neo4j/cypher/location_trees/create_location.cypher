MERGE (counter: Counter {name: 'location'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (location: Location {
  id: counter.count,
  name: $name,
  synonyms: $synonyms,
  description: $description,
  code: $code,
  address: $address
})
WITH
  location

// Link to type
CALL (location) {
  MATCH (type: LocationType {id: $type})
  CREATE (location)-[:OF_LOCATION_TYPE]->(type)
  RETURN collect(type.id)[0] as type
}
// Create coordinates, in order
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
    type: type,
    coordinates: coordinates
  }
