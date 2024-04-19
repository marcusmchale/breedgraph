MATCH
  (captured: Team {id: $team_id})
OPTIONAL MATCH (captured)-[:CONTRIBUTES_TO*]-(org:Team)
WITH captured, coalesce(collect(org), []) as teams
WITH captured + teams as teams
UNWIND teams as team
RETURN
  team.name as name,
  team.fullname as fullname,
  team.id as id,
  [(team)-[:CONTRIBUTES_TO]->(parent:Team) | parent.id][0] as parent_id,
  [(team)<-[:CONTRIBUTES_TO]-(child:Team) | child.id] as child_ids,
  [(team)-[:CONTRIBUTES_TO*]->(:Team)-[:ADMIN {authorisation:"AUTHORISED"}]->(admin:User) | admin.id] +
  coalesce(
    [(team)<-[:ADMIN {authorisation:"AUTHORISED"}]-(admin:User) | admin.id]
    , []
  ) + [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:ADMIN {authorisation:"AUTHORISED", heritable:True}]-(admin:User) | admin.id] as admin_ids
ORDER BY parent_id IS NOT NULL
// order by ensures the root node is first in the list
