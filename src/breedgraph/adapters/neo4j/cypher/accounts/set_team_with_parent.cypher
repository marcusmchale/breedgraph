MATCH
  (team: Team {id: $team})
MATCH
  (parent: Team {id: $parent})
OPTIONAL MATCH (team)-[contributes_to:CONTRIBUTES_TO]->(:Team)
DELETE contributes_to
CREATE (team)-[:CONTRIBUTES_TO]->(parent)
SET team.name = $name, team.name_lower = $name_lower, team.fullname = $fullname