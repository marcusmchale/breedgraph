MERGE (counter:Counter {name: 'team'})
  ON CREATE SET counter.count = 0
MERGE (team:Team {name: $name})
  ON CREATE SET
  counter.count = counter.count + 1,
  team.id = counter.count,
  team.fullname = $fullname
RETURN team
