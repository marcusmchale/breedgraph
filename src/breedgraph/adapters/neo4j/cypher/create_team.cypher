MERGE (counter:Counter {name: 'team'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (team: Team {
  id: counter.count,
  name: $name,
  name_lower: $name_lower,
  fullname: $fullname
})
RETURN team.name as name, team.fullname as fullname, team.id as id, null as parent_id
