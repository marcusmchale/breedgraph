UNWIND $edges as edge
MATCH (parent: GermplasmEntry {id:edge[0]})
MATCH (child: GermplasmEntry {id:edge[1]})
CREATE (parent)-[s:SOURCE_FOR]->(child)
SET s = edge[2]
return parent, child, s