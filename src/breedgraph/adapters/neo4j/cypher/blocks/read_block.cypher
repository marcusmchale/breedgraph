MATCH
  (captured: Unit {id: $unit_id})
OPTIONAL MATCH (captured)-[:INCLUDES_UNIT*]-(extended:Unit)
WITH captured, coalesce(collect(extended), []) AS units
WITH captured + units AS block
UNWIND block AS unit
MATCH (unit)-[:OF_GERMPLASM]->(germplasm:Germplasm)
RETURN unit {
  .*,
  subject: [(unit)-[:OF_SUBJECT]->(subject:Subject) | subject.id][0],
  germplasm: [(unit)-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0],
  positions: [
      (unit)-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location:Location) |
        position {.*, location:location.id, layout: [(position)-[:IN_LAYOUT]->(layout:Layout)|layout.id][0]}
    ],
  parent_id: [(parent:Unit)-[:INCLUDES_UNIT]->(unit)|parent.id][0]
}