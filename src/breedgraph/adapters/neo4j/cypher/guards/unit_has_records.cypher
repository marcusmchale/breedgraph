MATCH (unit: Unit {id: $unit_id})
RETURN EXISTS {
  MATCH (:Record)-[:FOR_UNIT]->(unit)
} as in_use
