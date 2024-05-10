MATCH (parent:Location {id: $parent})
MATCH (location_type: LocationType {id: $type})

MATCH (counter: Count {name: 'location'})
SET counter.count = counter.count + 1

CREATE (parent)<-[:WITHIN_LOCATION]-(l: Location {
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
