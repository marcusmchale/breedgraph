// Pending requests to be linked to Persons currently controlled by any of the given teams
MATCH (claimant: User)-[claims: CLAIMS]->(person: Person)
CALL (person) {
  MATCH (team: Team)-[:CONTROLS]->(:TeamPeople)-[:CONTROLS]->(control: Control)-[:CONTROLS]->(person)
  WITH team, control
  ORDER BY control.sequence DESC
  WITH team, collect(control)[0] AS latest_control
  WHERE NOT coalesce(latest_control.ended, false)
  RETURN collect(team.id) AS control_teams
}
WITH claimant, claims, person, control_teams
WHERE any(team_id IN control_teams WHERE team_id IN $team_ids)
RETURN person.id AS person_id, claimant.id AS user_id, claimant.name AS name, claimant.fullname AS fullname, claims.time AS time
ORDER BY claims.time
