MATCH (inviter: User {id: $invited_by})
MERGE (counter: Counter {name: 'invitation'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (inviter)-[:INVITED]->(invitation: Invitation {
  id:          counter.count,
  email:       $email,
  email_lower: $email_lower,
  created_at:  datetime.transaction(),
  expires_at:  datetime.transaction() + duration({days: $expiry_days})
})
WITH invitation
CALL (invitation) {
  UNWIND $teams AS offered
  MATCH (team: Team {id: offered.team_id})
  CREATE (invitation)-[:OFFERS_TEAM {access: offered.access}]->(team)
}
CALL (invitation) {
  MATCH (person: Person {id: $person_id})
  CREATE (invitation)-[:OFFERS_PERSON]->(person)
}
RETURN invitation {
  .id, .email, .created_at, .expires_at,
  invited_by: head([(inviter: User)-[:INVITED]->(invitation) | inviter.id]),
  teams: [(invitation)-[offer: OFFERS_TEAM]->(team: Team) | {team_id: team.id, access: offer.access}],
  person_id: head([(invitation)-[:OFFERS_PERSON]->(person: Person) | person.id])
} AS invitation
