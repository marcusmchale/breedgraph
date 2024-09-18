MATCH
  (unit: Unit) WHERE unit.id IN $unit_ids
OPTIONAL MATCH (unit)-[:IN_POSITION]->(position:Position)
DETACH DELETE unit, position
