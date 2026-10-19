MATCH (captured: Team)
WHERE captured.id IN $team_ids

// For each captured team, find its root by going up the hierarchy
OPTIONAL MATCH (captured)<-[:INCLUDES_TEAM*0..]-(root:Team)
WHERE NOT (root)<-[:INCLUDES_TEAM]-(:Team)  // root has no incoming INCLUDES

// Now get the complete organization starting from each root
OPTIONAL MATCH (root)-[:INCLUDES_TEAM*1..]->(member:Team)
WITH root, collect(DISTINCT member) AS team_tree_members
WITH root + team_tree_members AS team_tree

RETURN [ team IN team_tree |
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
] AS team_tree