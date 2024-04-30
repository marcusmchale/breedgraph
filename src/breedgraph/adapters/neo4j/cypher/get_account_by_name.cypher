MATCH
  (user:User {name_lower: ($name_lower)})

RETURN
  user {.*},
  [
    (user)-[affiliation:READ|WRITE|ADMIN]->(team:Team) |
    {
      team_id: team.id,
      authorisation: affiliation.authorisation,
      access:type(affiliation),
      heritable: affiliation.heritable
    }
  ] as affiliations,
  [
    (user)-[: ALLOWED_REGISTRATION]->(email:Email)|
    email.address
  ] AS allowed_emails


