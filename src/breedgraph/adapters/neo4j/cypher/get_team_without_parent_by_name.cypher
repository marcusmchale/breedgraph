MATCH
  (team: Team {name_lower: $name_lower})
OPTIONAL MATCH
  (team)-[:CONTRIBUTES_TO]->(parent:Team)
WITH team WHERE parent IS Null
RETURN team.name as name, team.fullname as fullname, team.id as id, NULL as parent_id