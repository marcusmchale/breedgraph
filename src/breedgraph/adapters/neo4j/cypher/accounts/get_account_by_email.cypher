MATCH
  (user:User {email_lower: ($email_lower)})

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
  ] as affiliations