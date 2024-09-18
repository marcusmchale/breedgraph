UNWIND $edges as edge
MATCH (parent: Unit {id:edge[0]})
MATCH (child: Unit {id:edge[1]})
CREATE (parent)-[:INCLUDES_UNIT {position: edge[2]}]->(child)
