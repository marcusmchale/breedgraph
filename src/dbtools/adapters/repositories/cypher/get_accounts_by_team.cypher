MATCH
  (user:User)
    -[:AFFILIATED]->(:Team {name: $team_name})
MATCH
  (user)-[affiliation:AFFILIATED]->(team:Team)
WITH user, affiliation, team
  ORDER BY affiliation.time ASC
WITH
  user,
  collect([team.name, team.fullname, affiliation.level]) AS affiliations
RETURN user, affiliations