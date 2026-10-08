// Only changed attributes are written: $props holds changed properties,
// and $teams, $claims are null when unchanged, as is $set_user false.
MATCH (person: Person {id: $id})
SET person += $props
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
  WHERE $set_user AND ($user IS NULL OR user.id <> $user)
  DELETE is_person
}
CALL (person) {
  MATCH (user: User {id: $user})
  WHERE $set_user
  MERGE (user)-[is_person: IS_PERSON]->(person)
  ON CREATE SET is_person.time = datetime.transaction()
}
CALL (person) {
  MATCH (claimant: User)-[claims: CLAIMS]->(person)
  WHERE NOT claimant.id IN $claims
  DELETE claims
}
CALL (person) {
  MATCH (claimant: User) WHERE claimant.id IN $claims
  MERGE (claimant)-[claims: CLAIMS]->(person)
  ON CREATE SET claims.time = datetime.transaction()
}
RETURN NULL
