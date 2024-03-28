MATCH
  (team: Team {id: $team_id})
MATCH
  (parent: Team {id: $parent_id})
OPTIONAL MATCH (team)-[contributes_to:CONTRIBUTES_TO]->(:Team)
DELETE contributes_to
CREATE (team)-[:CONTRIBUTES_TO]->(parent)
SET team.name = $name, team.name_lower = $name_lower, team.fullname = $fullname