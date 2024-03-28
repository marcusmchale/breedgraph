MATCH (team:Team {id:$team_id})
OPTIONAL MATCH (team)-[:CONTRIBUTES_TO]->(head:Team)
WHERE NOT (head)-[:CONTRIBUTES_TO]->(:Team)
WITH coalesce (head, team) as head
OPTIONAL MATCH p=(head)<-[:CONTRIBUTES_TO*]-(child:Team)
WHERE NOT (:Team)-[:CONTRIBUTES_TO]->(child)
WITH collect(p) AS ps
CALL apoc.convert.toTree(ps) YIELD value
RETURN value