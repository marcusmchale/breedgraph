MATCH (team:Team {id: $team})<-[:CONTRIBUTES_TO*]-(child:Team {id:$parent})
RETURN count(child) > 0

