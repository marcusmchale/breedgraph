MATCH (:User {id: $user_id})-[write:WRITE]->(:Team {id: $team_id})
DELETE WRITE
