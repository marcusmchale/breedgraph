UNWIND $edges as edge
MATCH (parent: Unit {id:edge[0]})
MATCH (child: Unit {id:edge[1]})
MERGE (parent)-[:INCLUDES_UNIT]->(child)
