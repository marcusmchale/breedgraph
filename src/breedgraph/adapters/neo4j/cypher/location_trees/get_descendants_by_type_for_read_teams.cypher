// Every location below the given locations that the given read teams can read, grouped by location type,
// as id and name only. For selecting all the locations of a type in a location tree at once, e.g. every field of a country.
MATCH (root:Location)
WHERE root.id IN $location_ids
MATCH (root)-[:INCLUDES_LOCATION*1..]->(location:Location)
WITH DISTINCT location
CALL (location) {
  OPTIONAL MATCH (location)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:TeamLocations)<-[:CONTROLS]-(team:Team)
  WITH team, control
  ORDER BY team.id, control.sequence DESC
  WITH team, collect(control)[0] AS control
  WHERE team IS NULL OR NOT coalesce(control.ended, false)
  RETURN collect(team.id) AS team_ids, collect(control.release) AS releases
}
WITH location,
  CASE
    WHEN size(team_ids) = 0 THEN true
    WHEN any(team_id IN team_ids WHERE team_id IN $read_teams) THEN true
    ELSE reduce(lowest = 2, release IN releases | CASE WHEN release < lowest THEN release ELSE lowest END) >= $minimum_release
  END AS readable
WHERE readable
OPTIONAL MATCH (location)-[:OF_LOCATION_TYPE]->(type:LocationType)
WITH type.id AS type, location
ORDER BY location.name, location.id
RETURN type, collect({id: location.id, name: location.name}) AS locations
