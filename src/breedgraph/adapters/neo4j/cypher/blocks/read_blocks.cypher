MATCH (root: Unit) WHERE NOT (root)<-[:INCLUDES_UNIT]-(:Unit)
OPTIONAL MATCH (root)-[:INCLUDES_UNIT*]->(child:Unit)
WITH root, coalesce(collect(child), []) AS children
WITH root + children AS block
RETURN [ unit in block |
  unit {
    .*,
    subject: [(unit)-[:OF_SUBJECT]->(subject:Subject) | subject.id][0],
    germplasm: [(unit)-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0],
    positions: [
      (unit)-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location:Location) |
        position {.*, location:location.id, layout: [(position)-[:IN_LAYOUT]->(layout:Layout)|layout.id][0]}
    ],
    parent_id: [(parent:Unit)-[:INCLUDES_UNIT]->(unit)|parent.id][0]
  }
] as block
