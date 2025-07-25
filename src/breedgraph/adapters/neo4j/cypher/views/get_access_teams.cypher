MATCH
  (user:User {id: ($user)})
RETURN {
  admin_teams: [(user)-[:ADMIN {authorisation:'AUTHORISED'}]->(team:Team)|team.id] + [(user)-[:ADMIN {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  read_teams: [(user)-[:READ {authorisation:'AUTHORISED'}]->(team:Team)|team.id] + [(user)-[:READ {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  write_teams: [(user)-[:WRITE {authorisation:'AUTHORISED'}]->(team:Team)|team.id] + [(user)-[:WRITE {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  curate_teams: [(user)-[:CURATE {authorisation:'AUTHORISED'}]->(team:Team)|team.id] + [(user)-[:CURATE {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES*]->(team)|team.id]
} as access_teams
