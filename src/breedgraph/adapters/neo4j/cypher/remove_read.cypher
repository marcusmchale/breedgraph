MATCH (:User {id: $user})-[read:READ]->(:Team {id: $team})
DELETE read