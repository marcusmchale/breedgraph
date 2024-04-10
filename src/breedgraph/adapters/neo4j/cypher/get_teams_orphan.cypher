MATCH
  (team: Team)
WHERE NOT (team)-[:CONTRIBUTES_TO]->(:Team)
RETURN team.name as name, team.fullname as fullname, team.id as id, NULL as parent_id

