MATCH
  (user:User {id: ($user_id)})
WITH
  user,
  [(user)-[:ADMIN {authorisation:'AUTHORISED'}]->(team:Team) | team.id] +
  [(user)-[:ADMIN {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    WHERE NOT (
      (user)-[:ADMIN {authorisation:"REVOKED"}]->(team) OR
      (user)-[:ADMIN {authorisation:"REVOKED", heritable: True}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    ) | team.id
  ] as admin_teams
RETURN admin_teams