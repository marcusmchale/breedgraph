MATCH (:User {id: $user_id})-[reads_from:READS_FROM]->(:Team {id: $team_id})
DELETE reads_from