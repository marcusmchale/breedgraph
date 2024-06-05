MATCH (person: Person {id: $person_id})<-[controls:CONTROLS]-(:TeamPeople)<-[:CONTROLS]-(team:Team)
WHERE team.id in $controllers
SET controls.release = $release

