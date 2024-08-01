MATCH (root: Location) WHERE NOT (root)-[:WITHIN_LOCATION]->(:Location)
OPTIONAL MATCH (root)<-[:WITHIN_LOCATION*]-(child:Location)

WITH root, coalesce(collect(child), []) AS children
WITH root + children AS locations
RETURN [ location in locations |
  location {
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
] as locations
