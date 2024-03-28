MATCH (head:Team {id:$id})
WHERE NOT (head)-[:CONTRIBUTES_TO]->(:Team)
OPTIONAL MATCH p=(head)<-[:CONTRIBUTES_TO*]-(child:Team)
WHERE NOT (:Team)-[:CONTRIBUTES_TO]->(child)
WITH head, collect(p) AS ps
CALL apoc.convert.toTree(ps) YIELD value
RETURN head, value


