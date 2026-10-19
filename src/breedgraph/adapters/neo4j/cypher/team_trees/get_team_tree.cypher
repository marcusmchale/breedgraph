MATCH
  (captured: Team {id: $team})
OPTIONAL MATCH (captured)-[includes:INCLUDES_TEAM*]-(org:Team)
WITH captured, coalesce(collect(org), []) AS teams
WITH captured + teams AS teams
UNWIND teams AS team
RETURN team {
  .*,
  affiliations: {
     ADMIN : [(team)<-[affiliation:ADMIN]-(user:User) | affiliation {.*, id: user.id}],
     READ : [(team)<-[affiliation:READ]-(user:User) | affiliation {.*, id: user.id}],
     WRITE : [(team)<-[affiliation:WRITE]-(user:User) | affiliation {.*, id: user.id}],
     CURATE : [(team)<-[affiliation:CURATE]-(user:User) | affiliation {.*, id: user.id}]
  }
}, [(team)-[include:INCLUDES_TEAM]->(member:Team) | [team.id, member.id, {label:type(include)}]] as includes
