MATCH (location: Location {id: $location})-[:OF_LOCATION_TYPE]->(t: LocationType)

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
