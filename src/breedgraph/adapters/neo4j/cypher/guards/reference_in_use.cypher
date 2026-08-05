MATCH (reference: Reference {id: $reference_id})
RETURN EXISTS {
  MATCH (reference)-[:REFERENCE_FOR]->()
} as in_use