MATCH (:User {id: $user_id})-[writes_for:WRITES_FOR]->(:Team {id: $team_id})
DELETE WRITES_FOR
