MATCH (:User {id: $user_id})-[admins_for:ADMINS_FOR]->(:Team {id: $team_id})
DELETE admins_for
