MATCH (person: Person)
WHERE person.name =~ $name_regex
RETURN person {
  .*,
  teams: [(person)-[:IN_TEAM]->(team: Team) | team.id],
  user: head([(user: User)-[:IS_PERSON]->(person) | user.id]),
  claims: [(claimant: User)-[:CLAIMS]->(person) | claimant.id]
} AS person
ORDER BY person.id
