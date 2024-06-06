MATCH
  (team: Team {id: $team})
SET team.name = $name, team.name_lower = $name_lower, team.fullname = $fullname
WITH team
OPTIONAL MATCH (team)-[contributes_to:CONTRIBUTES_TO]->(parent:Team)
WHERE NOT parent.id = $parent
DELETE contributes_to
WITH team
MATCH (parent: Team {id: $parent})
MERGE (team)-[contributes_to:CONTRIBUTES_TO]->(parent)
ON CREATE SET contributes_to.time = datetime.transaction()
