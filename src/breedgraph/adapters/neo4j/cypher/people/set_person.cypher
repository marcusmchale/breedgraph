MATCH (person: Person {id: $id})
SET
  person.name = $name,
  person.basis = $basis,
  person.orcid = $orcid,
  person.erased_at = $erased_at
WITH person
CALL (person) {
  MATCH (person)-[in_team: IN_TEAM]->(team: Team)
  WHERE NOT team.id IN $teams
  DELETE in_team
}
CALL (person) {
  MATCH (team: Team) WHERE team.id IN $teams
  MERGE (person)-[in_team: IN_TEAM]->(team)
  ON CREATE SET in_team.time = datetime.transaction()
}
CALL (person) {
  MATCH (user: User)-[is_person: IS_PERSON]->(person)
  WHERE $user IS NULL OR user.id <> $user
  DELETE is_person
}
CALL (person) {
  MATCH (user: User {id: $user})
  MERGE (user)-[:IS_PERSON]->(person)
}
RETURN NULL
