UNWIND $edges as edge
MATCH (parent: Germplasm {id:edge[0]})
MATCH (child: Germplasm {id:edge[1]})
CREATE (parent)-[s:SOURCE_FOR]->(child)
SET s = edge[2]
return parent, child, s