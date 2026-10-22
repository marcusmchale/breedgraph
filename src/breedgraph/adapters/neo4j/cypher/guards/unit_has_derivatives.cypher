MATCH (unit: Unit {id: $unit_id})
RETURN EXISTS {
  MATCH (:Unit)-[:DERIVED_FROM]->(unit)
} as in_use
