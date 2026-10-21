MATCH
  (user:User)-[affiliation]->(:Team)

WHERE type(affiliation) in $access_types
AND affiliation.authorisation in $authorisations
WITH DISTINCT user
RETURN user {.*}
