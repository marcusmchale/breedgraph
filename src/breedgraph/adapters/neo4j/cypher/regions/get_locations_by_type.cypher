MATCH
  (location: Location)-[:OF_LOCATION_TYPE]->(type:LocationType {id: $type})
RETURN location {
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