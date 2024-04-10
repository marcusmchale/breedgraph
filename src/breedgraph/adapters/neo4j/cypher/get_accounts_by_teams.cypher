MATCH
  (user:User)-[affiliation]->(team:Team)

WHERE
  team.id IN $team_ids AND
  type(affiliation) IN $access_types AND
  affiliation.authorisation in $authorisations

OPTIONAL MATCH
  (user)-[affiliation:READ|WRITE|ADMIN]->(team:Team)
OPTIONAL MATCH
  (team)<-[:CONTRIBUTES_TO*]-(inherited_team:Team)
  WHERE affiliation.heritable AND affiliation.authorisation = 'AUTHORISED'
  AND NOT (user)-[:READ|WRITE|ADMIN]->(inherited_team)
OPTIONAL MATCH
  (orphan:Team)
  WHERE NOT (orphan)-[:CONTRIBUTES_TO]->(:Team)
  AND NOT (user)-[:READ|WRITE|ADMIN]->(orphan)

WITH
  user {.*} as user,
  [(user)-[: ALLOWED_REGISTRATION]->(email:Email)|email.address] AS allowed_emails,
  collect(
    {
      team: team {.*, parent_id:[(team) - [:CONTRIBUTES_TO] - (parent:Team) | parent.id][0]},
      authorisation: affiliation.authorisation,
      access: type(affiliation)
    }
  )  +
  collect(distinct
    {
      team: inherited_team {.*, parent_id:[(team) - [:CONTRIBUTES_TO] - (parent:Team) | parent.id][0]},
      authorisation: affiliation.authorisation,
      access: type(affiliation)
    }
  )  +
    collect(distinct
    {
      team: orphan {.*},
      authorisation: NULL,
      access: NULL
    }
  )
  AS affiliations

RETURN
  user, allowed_emails, [a IN affiliations WHERE a.team IS NOT NULL] as affiliations