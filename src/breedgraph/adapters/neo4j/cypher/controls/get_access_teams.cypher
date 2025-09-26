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
  ] as admin_teams,
  [(user)-[:READ {authorisation:'AUTHORISED'}]->(team:Team) | team.id] +
  [(user)-[:READ {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    WHERE NOT (
      (user)-[:READ {authorisation:"REVOKED"}]->(team) OR
      (user)-[:READ {authorisation:"REVOKED", heritable: True}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    ) | team.id
  ] as read_teams,
  [(user)-[:WRITE {authorisation:'AUTHORISED'}]->(team:Team) | team.id] +
  [(user)-[:WRITE {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    WHERE NOT (
      (user)-[:WRITE {authorisation:"REVOKED"}]->(team) OR
      (user)-[:WRITE {authorisation:"REVOKED", heritable: True}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    ) | team.id
  ] as write_teams,
  [(user)-[:CURATE {authorisation:'AUTHORISED'}]->(team:Team) | team.id] +
  [(user)-[:CURATE {heritable:True, authorisation:'AUTHORISED'}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    WHERE NOT (
      (user)-[:CURATE {authorisation:"REVOKED"}]->(team) OR
      (user)-[:CURATE {authorisation:"REVOKED", heritable: True}]->(:Team)-[:INCLUDES_TEAM*]->(team)
    ) | team.id
  ] as curate_teams
RETURN {
  ADMIN: admin_teams,
  READ: read_teams,
  WRITE: write_teams,
  CURATE: curate_teams
} as access_teams