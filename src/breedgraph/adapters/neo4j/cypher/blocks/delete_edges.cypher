UNWIND $edges as edge
MATCH (:Unit {id:edge[0]})-[s:INCLUDES_UNIT]->(:Unit {id:edge[1]})
DELETE s