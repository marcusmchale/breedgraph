UNWIND $edges as edge
MATCH (:GermplasmEntry {id:edge[0]})-[s:SOURCE_FOR]->(:GermplasmEntry {id:edge[1]})
DELETE s