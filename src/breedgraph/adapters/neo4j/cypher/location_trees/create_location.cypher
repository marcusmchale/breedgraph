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
CALL {
  WITH location
  MATCH (type: LocationType {id: $type})
  CREATE (location)-[:OF_LOCATION_TYPE]->(type)
  RETURN collect(type.id)[0] as type
}
// Create coordinates
CALL {
  WITH location
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
    type: type,
    coordinates: coordinates
  }
