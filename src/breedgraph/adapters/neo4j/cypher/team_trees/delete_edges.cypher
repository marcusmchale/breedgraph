unwind $edges as edge
MATCH (: Team {id:edge[0]})-[includes:INCLUDES_TEAM]->(: Team {id:edge[1]})
DELETE includes