MATCH (:User {id: $user})-[curate:CURATE]->(:Team {id: $team})
DELETE curate
