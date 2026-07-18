MATCH (study: Study {id: $study_id})
RETURN {
  EXISTS (dataset: Dataset)-[:FOR_STUDY]->(study)
} as in_use