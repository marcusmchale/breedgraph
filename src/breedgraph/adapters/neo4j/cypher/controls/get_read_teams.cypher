MATCH
  (user:User {id: ($user_id)})
WITH
  user,
  [(user)-[:READ {authorisation:'AUTHORISED'}]->(team:Team) | team.id] +
  [(user)-[:READ {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    WHERE NOT (
      (user)-[:READ {authorisation:"REVOKED"}]->(team) OR
      (user)-[:READ {authorisation:"REVOKED", heritable: True}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    ) | team.id
  ] as read_teams
RETURN read_teams