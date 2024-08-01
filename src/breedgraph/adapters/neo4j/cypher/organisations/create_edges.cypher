unwind $edges as edge
MATCH (parent: Team {id:edge[0]})
MATCH (child: Team {id:edge[1]})
CREATE (parent)-[:INCLUDES]->(child)