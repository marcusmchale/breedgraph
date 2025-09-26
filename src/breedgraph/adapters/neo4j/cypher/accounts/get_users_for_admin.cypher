MATCH (team: Team)
    <-[:READ|WRITE|ADMIN|CURATE]-(user:User)
WHERE team.id in $team_ids
AND user.id in $user_ids
WITH distinct user
RETURN
  user {
    id: user.id,
    name: user.name,
    fullname: user.fullname,
    email: user.email,
    ontology_role: user.ontology_role,
    email_verified: user.email_verified
  }