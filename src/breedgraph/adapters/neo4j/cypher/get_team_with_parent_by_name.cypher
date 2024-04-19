MATCH
  (team: Team {name_lower: $name_lower})-[:CONTRIBUTES_TO]->(parent:Team {id:$parent_id})
RETURN
  team.name as name,
  team.fullname as fullname,
  team.id as id,
  parent.id as parent_id