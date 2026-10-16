UNWIND $edges as edge
MATCH (:Location {id:edge[0]})-[s:INCLUDES_LOCATION]->(:Location {id:edge[1]})
DELETE s