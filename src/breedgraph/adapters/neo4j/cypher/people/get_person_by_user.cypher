MATCH (user: User {id: $user_id})-[:IS_PERSON]->(person: Person)
RETURN person {
  .*,
  teams: [(person)-[:IN_TEAM]->(team: Team) | team.id],
  user: user.id,
  claims: [(claimant: User)-[:CLAIMS]->(person) | claimant.id]
} AS person
