MATCH (unit: Unit {id: $unit_id})
RETURN EXISTS {
  MATCH (:Germplasm)-[:FROM_UNIT]->(unit)
} as in_use
