MATCH (:User {id: $user_id})-[read:READ]->(:Team {id: $team_id})
DELETE read