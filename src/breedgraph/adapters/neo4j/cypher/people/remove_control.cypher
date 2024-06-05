MATCH (: Person {id: $person_id})<-[controls:CONTROLS]-(:TeamPeople)<-[:CONTROLS]-(:Team {id:$team_id})
DELETE controls