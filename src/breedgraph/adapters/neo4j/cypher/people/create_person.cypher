MERGE (counter: Counter {name: 'person'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (person: Person {
  id:                   counter.count,
  name:                 $name,
  basis:                $basis,
  informed_attestation: $informed_attestation,
  recorded_by:          $recorded_by,
  recorded_at:          datetime.transaction()
})
WITH person
CALL (person) {
  MATCH (team: Team) WHERE team.id IN $teams
  CREATE (person)-[:IN_TEAM {time: datetime.transaction()}]->(team)
}
RETURN person {
  .*,
  teams: [(person)-[:IN_TEAM]->(team: Team) | team.id],
  user: null
} AS person
