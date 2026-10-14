// The locations of a type that the given read teams can read: with no current controls, when the least of their
// current controls' releases is at least $minimum_release, or when a team in $read_teams controls them
MATCH (location: Location)-[:OF_LOCATION_TYPE]->(type:LocationType {id: $location_type})
CALL (location) {
  OPTIONAL MATCH (location)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:TeamLocations)<-[:CONTROLS]-(team:Team)
  WITH team, control
  ORDER BY team.id, control.sequence DESC
  WITH team, collect(control)[0] AS control
  WHERE team IS NULL OR NOT coalesce(control.ended, false)
  RETURN collect(team.id) AS team_ids, collect(control.release) AS releases
}
WITH location, type,
  CASE
    WHEN size(team_ids) = 0 THEN true
    WHEN any(team_id IN team_ids WHERE team_id IN $read_teams) THEN true
    ELSE reduce(lowest = 2, release IN releases | CASE WHEN release < lowest THEN release ELSE lowest END) >= $minimum_release
  END AS readable
WHERE readable

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