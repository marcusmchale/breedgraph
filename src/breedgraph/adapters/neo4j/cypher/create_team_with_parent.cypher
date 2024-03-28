MERGE (counter:Counter {name: 'team'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
MATCH (parent: Team {id: $parent_id})
CREATE (team: Team {
  id: counter.count,
  name: $name,
  name_lower: $name_lower,
  fullname: $fullname
})-[:CONTRIBUTES_TO]->(parent)
RETURN team.name as name, team.fullname as fullname, team.id as id, parent.id as parent_id