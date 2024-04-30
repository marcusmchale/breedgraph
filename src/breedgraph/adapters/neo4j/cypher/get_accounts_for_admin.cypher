MATCH
  (admin:User {id:$user})
WITH
coalesce([(admin)-[:ADMIN {authorisation: 'AUTHORISED'}]->(team:Team) | team], []) +
[(admin)-[:ADMIN {heritable:True, authorisation: 'AUTHORISED'}]->(:Team)<-[:CONTRIBUTES_TO*]-(team: Team) | team] as teams
UNWIND teams as team
MATCH
  (team)<-[affiliation:READ|WRITE|ADMIN]-(user: User)


RETURN
  user {
    .id, .fullname, .email
  },
  collect({
    team_id: team.id,
    authorisation: affiliation.authorisation,
    access: type(affiliation),
    heritable: affiliation.heritable
  }) as affiliations