MATCH
  (user:User {id: ($user_id)})-[:READ|WRITE|ADMIN]->(team:Team)
OPTIONAL MATCH
  (user)-[:READ|WRITE|ADMIN {heritable:True, authorisation:"AUTHORISED"}]->(:Team)
    <-[:CONTRIBUTES_TO*]-(inherited_team:Team)
WITH collect(team) + collect(inherited_team) as teams
UNWIND teams as team
OPTIONAL MATCH
  (team)-[:CONTRIBUTES_TO]->(parent:Team)

RETURN
  team.name as name,
  team.fullname as fullname,
  team.id as id,
  NULL as parent_id