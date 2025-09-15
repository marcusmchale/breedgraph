MATCH (root: Team) WHERE NOT (root)<-[:INCLUDES_TEAM]-(:Team)
OPTIONAL MATCH (root)-[:INCLUDES_TEAM*]->(child:Team)
WITH root, coalesce(collect(child), []) AS children
WITH root + children AS organisation
RETURN [ team IN organisation |
  team {
    . *,
    affiliations:{
    ADMIN:[(team)< - [affiliation:ADMIN] -(user:User) | affiliation {. *, id:user.id}],
    READ:[(team)< - [affiliation:READ] -(user:User) | affiliation {. *, id:user.id}],
    WRITE:[(team)< - [affiliation:WRITE] -(user:User) | affiliation {. *, id:user.id}],
    CURATE:[(team)< - [affiliation:CURATE] -(user:User) | affiliation {. *, id:user.id}]
    },
    includes: [(team)- [includes:INCLUDES_TEAM] - >(member:Team) | [team.id, member.id, {label:type(includes)}]]
  }
] AS organisation
