MATCH
  (user:User)-[:ALLOWED_REGISTRATION]->(email:Email {address_lower: $email_lower})
RETURN
  user {.*},
  [
    (user)-[affiliation:READ|WRITE|ADMIN]->(team:Team) |
    {
      team: team.id,
      authorisation: affiliation.authorisation,
      access: type(affiliation),
      heritable: affiliation.heritable,
      inherits_to: [(team)<-[:CONTRIBUTES_TO*]-(tt:Team)|tt.id],
      admins: coalesce([(team)<-[:ADMIN {authorisation:"AUTHORISED"}]-(admin:User )| admin.id], []) +
      [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:ADMIN {authorisation:"AUTHORISED", heritable:True}]-(admin:User )|admin.id]
    }
  ] as affiliations,
  [(user)-[: ALLOWED_REGISTRATION]->(email:Email)|email.address] AS allowed_emails,
  [(user)-[: ALLOWED_REGISTRATION]->(invited:User)| invited.id] as allowed_users