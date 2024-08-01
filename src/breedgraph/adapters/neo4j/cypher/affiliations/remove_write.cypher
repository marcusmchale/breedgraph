MATCH (:User {id: $user})-[write:WRITE]->(:Team {id: $team})
DELETE write
