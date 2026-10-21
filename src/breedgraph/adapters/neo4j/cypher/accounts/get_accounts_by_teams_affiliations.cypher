MATCH
  (user:User)-[affiliation]->(match_team:Team)

WHERE type(affiliation) in $access_types
AND affiliation.authorisation in $authorisations
AND match_team.id in $teams
WITH DISTINCT user
RETURN user {.*}
