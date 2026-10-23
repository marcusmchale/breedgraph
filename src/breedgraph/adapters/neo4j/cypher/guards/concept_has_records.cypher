MATCH (concept: Variable|Factor {id: $concept_id})
RETURN EXISTS {
  MATCH (concept)<-[:FOR_CONCEPT]-(:Dataset)-[:INCLUDES_RECORD]->(:Record)
} as in_use
