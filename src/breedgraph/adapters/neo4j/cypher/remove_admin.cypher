MATCH (:User {id: $user_id})-[admin:ADMIN]->(:Team {id: $team_id})
DELETE admin
