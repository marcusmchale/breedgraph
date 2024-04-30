MATCH
  (captured: Team {id: $team})
OPTIONAL MATCH (captured)-[:CONTRIBUTES_TO*]-(org:Team)
WITH captured, coalesce(collect(org), []) AS teams
WITH captured + teams AS teams
UNWIND teams AS team
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
ORDER BY team.parent IS NOT NULL
// order by ensures the root node is first in the list
