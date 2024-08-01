MATCH (:User {id: $user})-[admin:ADMIN]->(:Team {id: $team})
DELETE admin
