MATCH (t:Team {id: $team})-[contributes_to:CONTRIBUTES_TO]->(:Team)
DELETE contributes_to