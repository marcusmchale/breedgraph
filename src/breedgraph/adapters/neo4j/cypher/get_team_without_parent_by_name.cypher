MATCH
  (team: Team {name_lower: $name_lower})
WHERE NOT
  (team)-[:CONTRIBUTES_TO]->(parent:Team)
RETURN
  team.name as name,
  team.fullname as fullname,
  team.id as id,
  NULL as parent_id