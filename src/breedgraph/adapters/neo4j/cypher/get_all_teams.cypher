MATCH
  (team: Team)
OPTIONAL MATCH (team)-[:CONTRIBUTES_TO]->(parent:Team)
RETURN team.name as name, team.fullname as fullname, team.id as id, parent.id as parent_id

