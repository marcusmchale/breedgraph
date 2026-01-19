MATCH (reference: Reference {id: $reference_id})
RETURN {
  EXISTS (reference)-[:REFERENCE_FOR]->()
} as in_use