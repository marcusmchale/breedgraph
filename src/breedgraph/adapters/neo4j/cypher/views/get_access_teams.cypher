MATCH
  (user:User {id: ($user)})
RETURN {
  ADMIN: [(user)-[:ADMIN {authorisation:'AUTHORISED'}]->(team:Team)|team.id] + [(user)-[:ADMIN {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  READ: [(user)-[:READ {authorisation:'AUTHORISED'}]->(team:Team)|team.id] + [(user)-[:READ {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  WRITE: [(user)-[:WRITE {authorisation:'AUTHORISED'}]->(team:Team)|team.id] + [(user)-[:WRITE {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES*]->(team)|team.id],
  CURATE: [(user)-[:CURATE {authorisation:'AUTHORISED'}]->(team:Team)|team.id] + [(user)-[:CURATE {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES*]->(team)|team.id]
} as access_teams
