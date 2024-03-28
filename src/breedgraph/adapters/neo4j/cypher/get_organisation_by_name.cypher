MATCH (head:Team {name_lower:$name_lower})
WHERE NOT (head)-[:CONTRIBUTES_TO]->(:Team)
OPTIONAL MATCH p=(head)<-[:CONTRIBUTES_TO*]-(child:Team)
WHERE NOT (:Team)-[:CONTRIBUTES_TO]->(child)
WITH collect(p) AS ps
CALL apoc.convert.toTree(ps) YIELD value
RETURN value