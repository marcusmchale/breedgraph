MATCH (person: Person)
RETURN person {
  .*,
  teams: [(person)-[:IN_TEAM]->(team: Team) | team.id],
  user: head([(user: User)-[:IS_PERSON]->(person) | user.id])
} AS person
ORDER BY person.id
