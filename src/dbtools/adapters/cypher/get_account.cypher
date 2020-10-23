MATCH
  (user: User {username_lower: ($username_lower)})
    -[affiliation: AFFILIATED]->(team: Team)
WITH user, affiliation, team ORDER BY affiliation.time ASC
WITH
  user,
  collect([team.name, team.fullname, affiliation.level]) as affiliations
return user, affiliations