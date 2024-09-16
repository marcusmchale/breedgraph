UNWIND $edges as edge
MATCH (parent: Location {id:edge[0]})
MATCH (child: Location {id:edge[1]})
CREATE (parent)-[:INCLUDES_LOCATION]->(child)
return parent, child