MATCH
  (user:User)-[affiliation]->(:Team)

WHERE type(affiliation) in $access_types
AND affiliation.authorisation in $authorisations

OPTIONAL MATCH
  (user)-[affiliation:READ|WRITE|ADMIN]->(team:Team)
OPTIONAL MATCH
  (team)<-[:CONTRIBUTES_TO*]-(inherited_team:Team)
  WHERE affiliation.heritable AND affiliation.authorisation = 'AUTHORISED'
  AND NOT (user)-[:READ|WRITE|ADMIN]->(inherited_team)
OPTIONAL MATCH
  (team)<-[request:READ|WRITE|ADMIN {authorisation: 'REQUESTED'}]-(requesting_user)
  WHERE type(affiliation) = 'ADMIN' AND affiliation.authorisation = 'AUTHORISED'
OPTIONAL MATCH
  (inherited_team)<-[inherited_request:READ|WRITE|ADMIN {authorisation: 'REQUESTED'}]-(inherited_requesting_user)
  WHERE type(affiliation) = 'ADMIN'

WITH
  user,
  [(user)-[: ALLOWED_REGISTRATION]->(email:Email)|email.address] AS allowed_emails,
  collect({
      user_id: user.id,
      team_id: team.id,
      authorisation: affiliation.authorisation,
      access: type(affiliation)
  })  +
  collect(DISTINCT {
      user_id: user.id,
      team_id: inherited_team.id,
      authorisation: affiliation.authorisation,
      access: type(affiliation)
  }) +
  collect(DISTINCT {
      user_id: requesting_user.id,
      team_id: team.id,
      authorisation: request.authorisation,
      access: type(request)
  }) +
  collect(DISTINCT {
      user_id: inherited_requesting_user.id,
      team_id: inherited_team.id,
      authorisation: inherited_request.authorisation,
      access: type(affiliation)
  }) as affiliations

OPTIONAL MATCH
  (root:Team)
  WHERE NOT (root)-[:CONTRIBUTES_TO]->(:Team)
  AND NOT (user)-[:READ|WRITE|ADMIN]->(root)

WITH
  user,
  allowed_emails,
  affiliations,
  collect({
      user_id: user.id,
      team_id: root.id,
      authorisation: NULL,
      access: NULL
  }) as root_affiliations

return
  user,
  allowed_emails,
  [
    a in affiliations+root_affiliations
      WHERE a.team_id IS NOT NULL and a.user_id IS NOT NULL
  ] as affiliations
