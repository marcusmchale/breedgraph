MATCH (captured: Team)
WHERE captured.id IN $team_ids

// For each captured team, find its root by going up the hierarchy
OPTIONAL MATCH (captured)<-[:INCLUDES_TEAM*0..]-(root:Team)
WHERE NOT (root)<-[:INCLUDES_TEAM]-(:Team)  // root has no incoming INCLUDES

// Now get the complete organization starting from each root
OPTIONAL MATCH (root)-[:INCLUDES_TEAM*1..]->(member:Team)
WITH root, collect(DISTINCT member) AS organisation_members
WITH root + organisation_members AS organisation

RETURN [ team IN organisation |
  team {
    .*,
    affiliations:{
      ADMIN:[(team)<-[affiliation:ADMIN]-(user:User) | affiliation {.*, id:user.id}],
      READ:[(team)<-[affiliation:READ]-(user:User) | affiliation {.*, id:user.id}],
      WRITE:[(team)<-[affiliation:WRITE]-(user:User) | affiliation {.*, id:user.id}],
      CURATE:[(team)<-[affiliation:CURATE]-(user:User) | affiliation {.*, id:user.id}]
    },
    includes: [(team)-[includes:INCLUDES_TEAM]->(child:Team) | [team.id, child.id, {label:type(includes)}]]
  }
] AS organisation