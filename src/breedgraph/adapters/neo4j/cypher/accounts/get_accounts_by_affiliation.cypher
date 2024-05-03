MATCH
  (user:User)-[affiliation]->(:Team)

WHERE type(affiliation) in $access_types
AND affiliation.authorisation in $authorisations

RETURN
  user {.*},
  [
    (user)-[affiliation:READ|WRITE|ADMIN]->(team:Team) |
    {
      team_id: team.id,
      authorisation: affiliation.authorisation,
      access: type(affiliation),
      heritable: affiliation.heritable
    }
  ] as affiliations,
  [(user)-[: ALLOWED_REGISTRATION]->(email:Email)|email.address] AS allowed_emails,
  [(user)-[: ALLOWED_REGISTRATION]->(invited:User)| invited.id] as allowed_users
