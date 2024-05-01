MATCH
  (admin:User {id:$user})
WITH
coalesce([(admin)-[:ADMIN {authorisation: 'AUTHORISED'}]->(team:Team) | team], []) +
[(admin)-[:ADMIN {heritable:True, authorisation: 'AUTHORISED'}]->(:Team)<-[:CONTRIBUTES_TO*]-(team: Team) | team] as teams
UNWIND teams as team
CALL {
  WITH team
  MATCH (user: User)-[affiliation:READ|WRITE|ADMIN]->(team)
  RETURN
    coalesce(collect(user), []) as users
}
CALL {
  WITH team
  OPTIONAL MATCH (user: User)-[affiliation:READ|WRITE|ADMIN {heritable:True}]->(:Team)<-[:CONTRIBUTES_TO*]-(team)
  RETURN
    coalesce(collect(user), []) as inherited_users
}
WITH users + inherited_users as users
UNWIND users as user
RETURN DISTINCT user {.id, .name, .fullname, .email}
