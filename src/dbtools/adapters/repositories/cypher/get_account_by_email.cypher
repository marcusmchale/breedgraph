MATCH
  (user:User {email: ($email)})-[affiliation:AFFILIATED]->(team:Team)
WITH user, affiliation, team
  ORDER BY affiliation.time ASC
WITH
  user,
  collect([team.name, team.fullname, affiliation.level]) AS affiliations
RETURN user, affiliations