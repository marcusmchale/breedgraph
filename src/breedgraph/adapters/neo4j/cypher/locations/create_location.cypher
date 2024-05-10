MATCH (country:Country {code: $country})
MATCH (location_type: LocationType {id: $type})
MERGE (counter: Count {name: 'location'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1

CREATE (c)<-[:WITHIN_LOCATION]-(l: Location {
  id: counter.count,
  code: $code,
  name: $name,
  fullname: $fullname,
  description: $description,
  address: $address
})-[:OF_LOCATION_TYPE]->(t)
WITH l
UNWIND $coordinates as c
CREATE (l)<-[:COORDINATE_OF]-(:Coordinate {
  sequence: c.sequence,
  latitude: c.latitude,
  longitude: c.longitude,
  altitude: c.altitude,
  uncertainty: c.uncertainty,
  description: c.description
})
