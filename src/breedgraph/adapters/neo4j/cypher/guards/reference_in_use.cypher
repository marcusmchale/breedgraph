MATCH (reference: Reference {id: $reference_id})
RETURN EXISTS {
  MATCH (reference)-[:REFERENCE_FOR]->()
} OR EXISTS {
  MATCH (reference)<-[:USES_LICENCE|USES_COPYRIGHT]-()
} as in_use
