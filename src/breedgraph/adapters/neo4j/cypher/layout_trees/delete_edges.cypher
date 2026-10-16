UNWIND $edges as edge
MATCH (:Layout {id:edge[0]})-[s:INCLUDES_LAYOUT]->(:Layout {id:edge[1]})
DELETE s