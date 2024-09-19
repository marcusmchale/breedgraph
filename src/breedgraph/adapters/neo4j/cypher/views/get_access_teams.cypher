MATCH
  (user:User {id: ($user)})
RETURN {
  admin_teams: [(user)-[:ADMIN]->(team:Team)|team.id] + [(user)-[:ADMIN {heritable:True}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  read_teams: [(user)-[:READ]->(team:Team)|team.id] + [(user)-[:READ {heritable:True}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  write_teams: [(user)-[:WRITE]->(team:Team)|team.id] + [(user)-[:WRITE {heritable:True}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  curate_teams: [(user)-[:CURATE]->(team:Team)|team.id] + [(user)-[:CURATE {heritable:True}]->(:Team)-[:INCLUDES*]->(team)|team.id]
} as access_teams
