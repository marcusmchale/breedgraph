MATCH (admin: User {id: $user})
WITH [(user)-[:ADMIN]->(team:Team)|team] +
     [(user)-[:ADMIN {heritable:True}]->(:Team)-[:INCLUDES*]->(team)|team]
AS admin_teams
UNWIND admin_teams as team
MATCH (user)-[:READ|WRITE|ADMIN|CURATE]->(team)
RETURN user {.id, .name, .fullname, .email}
