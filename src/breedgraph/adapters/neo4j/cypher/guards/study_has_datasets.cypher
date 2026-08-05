MATCH (study: Study {id: $study_id})
RETURN EXISTS{
  MATCH (dataset: Dataset)-[:FOR_STUDY]->(study)
} as in_use