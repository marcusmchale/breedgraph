MATCH
  (captured: Location {id: $location})
OPTIONAL MATCH (captured)-[:WITHIN_LOCATION*]-(extended:Location)

WITH captured, coalesce(collect(extended), []) AS locations
WITH captured + locations AS region
UNWIND region AS location
WITH location {
  .*,
  parent: [(location)-[:WITHIN_LOCATION]->(parent:Location) | parent.id][0],
  children: [(location)<-[:WITHIN_LOCATION]-(child:Location) | child.id],
  type: [(location)-[:OF_LOCATION_TYPE]->(type:LocationType) | type.id][0],
  coordinates: [(location)<-[:COORDINATE_OF]-(coordinate:Coordinate) | coordinate {.*}],
  controller: {
      controls: [
        (location)<-[controls:CONTROLS]-(:TeamLocations)<-[:CONTROLS]-(team:Team) |
        {team: team.id, release: controls.release, time: controls.time}
      ],
      writes: [
        (person)<-[write:CREATED|UPDATED]-(:UserLocations)<-[:CREATED]-(user:User) |
        {user:user.id, time: write.time}
      ]
    }
}
RETURN collect(location) as locations
