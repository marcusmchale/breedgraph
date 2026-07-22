MATCH (team: Team)
    <-[:READ|WRITE|ADMIN|CURATE]-(user:User)
WHERE team.id in $admin_teams
AND user.id in $user_ids
WITH distinct user
RETURN
  user {
    id: user.id,
    name: user.name,
    fullname: user.fullname,
    ontology_role: user.ontology_role
  }