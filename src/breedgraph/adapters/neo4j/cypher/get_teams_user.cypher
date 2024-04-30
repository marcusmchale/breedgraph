MATCH
  (user:User {id: ($user)})
WITH
  coalesce([(user)-[affiliation:READ|WRITE|ADMIN]->(team:Team) | team ], []) +
  [(user)-[affiliation:READ|WRITE|ADMIN {heritable: True, authorisation: 'AUTHORISED'}]->(:Team)<-[:CONTRIBUTES_TO*]-(team) | team]
  as teams
CALL {
  MATCH (root: Team)
  WHERE NOT (root)-[:CONTRIBUTES_TO]->(:Team)
  return collect(root) as roots
}
WITH teams + roots as teams
UNWIND teams as team
WITH DISTINCT team

RETURN team {
  .*,
  parent: [(team)-[:CONTRIBUTES_TO]->(parent:Team) | parent.id][0],
  children: [(team)<-[:CONTRIBUTES_TO]-(child:Team) | child.id],
  readers: coalesce([(team)<-[:READ {authorisation:"AUTHORISED"}]-(reader:User) | reader.id], []) +
       [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:READ {authorisation:"AUTHORISED", heritable:true}]-(reader:User) | reader.id],
  writers: [(team)<-[:WRITE {authorisation:"AUTHORISED"}] -(writer:User) | writer.id],
  admins: coalesce([(team)<-[:ADMIN {authorisation:"AUTHORISED"}] -(admin:User) | admin.id], []) +
       [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:ADMIN {authorisation:"AUTHORISED", heritable:true}]-(admin:User) | admin.id],
  requests: [(team)<-[:READ|WRITE|ADMIN {authorisation:"REQUESTED"}]-(request:User) | request.id]
}