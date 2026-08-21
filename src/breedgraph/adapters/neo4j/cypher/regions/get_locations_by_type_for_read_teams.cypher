MATCH
(location: Location)-[:OF_LOCATION_TYPE]->(type:LocationType {id: $location_type}),
(location)<-[:CONTROLS]-(control:Control)
  <-[:CONTROLS]-(:TeamLocations)
  <-[:CONTROLS]-(team:Team)

WITH location, type, team, control
ORDER by location.id, team.id, control.sequence DESC

WITH location, type, team, collect(control)[0] as control
WITH location, type, collect(team.id) as team_ids, collect(control.release) as releases

WITH location, type, team_ids, min(releases) as effective_release
WHERE any(team_id in team_ids WHERE team_id in $read_teams)
OR effective_release >= $minimum_release

WITH DISTINCT location, type

OPTIONAL MATCH (parent:Location)-[:INCLUDES_LOCATION]->(location)

OPTIONAL MATCH (root:Location)-[:INCLUDES_LOCATION*]->(location)
WHERE NOT (root)<-[:INCLUDES_LOCATION]-(:Location)

OPTIONAL CALL (location) {
  MATCH (location)<-[coord_of:COORDINATE_OF]-(coordinate:Coordinate)
  WITH coordinate, coord_of
  ORDER BY coord_of.position
  RETURN collect(coordinate {.*}) as coordinates
}

OPTIONAL CALL (location) {
  MATCH (location)-[:INCLUDES_LOCATION]->(child: Location)
  RETURN collect(child.id) as children
}

RETURN location {
  .*,
  type: type.id,
  coordinates: coalesce(coordinates, []),
  region: coalesce(root.id, location.id),
  parent: parent.id,
  children: coalesce(children, [])
}