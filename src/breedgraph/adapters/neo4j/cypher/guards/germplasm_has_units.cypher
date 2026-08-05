MATCH (germplasm: Germplasm {id: $germplasm_id})
RETURN EXISTS {
  MATCH (:Unit)-[:OF_GERMPLASM]->(germplasm)
} as in_use