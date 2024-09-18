UNWIND $edges as edge
MATCH (:Germplasm {id:edge[0]})-[s:SOURCE_FOR]->(:Germplasm {id:edge[1]})
DELETE s