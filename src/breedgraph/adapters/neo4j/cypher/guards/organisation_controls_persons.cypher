// Whether any team of the organisation currently controls a Person, including erased Persons
MATCH (root: Team {id: $team_id})-[:INCLUDES_TEAM*0..]->(team: Team)
RETURN EXISTS {
  MATCH (team)-[:CONTROLS]->(:TeamPeople)-[:CONTROLS]->(control: Control)-[:CONTROLS]->(person: Person)
  WITH team, person, control
  ORDER BY control.sequence DESC
  WITH team, person, collect(control)[0] AS latest_control
  WHERE NOT coalesce(latest_control.ended, false)
  RETURN person
} AS in_use
