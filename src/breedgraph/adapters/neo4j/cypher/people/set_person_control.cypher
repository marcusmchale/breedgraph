MATCH (person: Person {id: $person_id})
MATCH (team:Team {id:$team_id})
MERGE (team)-[:CONTROLS]->(tp:TeamPeople)
MERGE (tp)-[controls:CONTROLS]->(person)
ON CREATE SET controls.time = datetime.transaction()
SET controls.release = $release