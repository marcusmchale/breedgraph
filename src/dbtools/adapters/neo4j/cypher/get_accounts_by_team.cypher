MATCH
  (user:User)
    -[affiliated:AFFILIATED]->(team:Team {id: $team_id})
OPTIONAL MATCH
  (team)<-[admin_affiliated:AFFILIATED]-(admin:User)
WHERE admin_affiliated.levels[-1] = 2
WITH user, affiliated, team, collect(admin) as admins
  ORDER BY affiliated.times[0] ASC
WITH
  user,
  collect(team, affiliated, admins) AS affiliations
RETURN user, affiliations
