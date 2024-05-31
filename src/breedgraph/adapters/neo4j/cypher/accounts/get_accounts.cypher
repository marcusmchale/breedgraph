MATCH
  (user:User)
WHERE user.id in $user_ids
RETURN
  user {.*},
  [
    (user)-[affiliation:READ|WRITE|ADMIN]->(team:Team) |
    {
      team: team.id,
      teams: [team.id] + [(team)<-[:CONTRIBUTES_TO*]-(tt:Team)|tt.id],
      admins: coalesce([(team)<-[:ADMIN {authorisation:"AUTHORISED"}]-(admin:User )|admin.id], []) +
      [(team)-[:CONTRIBUTES_TO]->(:Team)<-[:ADMIN {authorisation:"AUTHORISED", heritable:True}]-(admin:User)|admin.id],
      authorisation: affiliation.authorisation,
      access: type(affiliation),
      heritable: affiliation.heritable
    }
  ] as affiliations,
  [(user)-[: ALLOWED_REGISTRATION]->(email:Email)|email.address] AS allowed_emails,
  [(user)-[: ALLOWED_REGISTRATION]->(invited:User)| invited.id] as allowed_users