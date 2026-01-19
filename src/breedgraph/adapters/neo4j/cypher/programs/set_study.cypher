MATCH
  (study: Study {id: $study_id})
SET study += $study_data
WITH study
// Update references
CALL {
  WITH study
  MATCH (reference:Reference)-[reference_for:REFERENCE_FOR]->(study)
    WHERE NOT reference.id IN $reference_ids
  DELETE reference_for
}
CALL {
  WITH study
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  MERGE (reference)-[reference_for:REFERENCE_FOR]->(study)
}
// Update Datasets
CALL {
  WITH study
  MATCH (study)-[has_dataset:HAS_DATASET]->(dataset: Dataset) WHERE NOT dataset.id IN $dataset_ids
  DELETE has_dataset
}
CALL {
  WITH study
  MATCH (dataset: Dataset) WHERE dataset.id IN $dataset_ids
  MERGE (study)-[:HAS_DATASET]->(dataset)
}
//Update design (in ontology)
CALL {
  WITH study
  MATCH (study)-[has_design:USES_DESIGN]->(design:Design)
    WHERE NOT design.id = $design_id
  DELETE has_design
}
CALL {
  WITH study
  MATCH (design: Design {id :$design_id})
  MERGE (study)-[:USES_DESIGN]->(design)
}
//Update licence (reference)
CALL {
  WITH study
  MATCH (study)-[uses_licence:USES_LICENCE]->(licence:Reference)
    WHERE NOT licence.id = $licence_id
  DELETE uses_licence
}
CALL {
  WITH study
  MATCH (licence: Reference {id: $licence_id})
  MERGE (study)-[:USES_LICENCE]->(licence)
}
RETURN NULL
