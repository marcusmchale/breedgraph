MATCH
  (study: Study {id: $study_id})
SET study += $study_data
WITH study
// Update references
CALL (study) {
  OPTIONAL MATCH (reference:Reference)-[reference_for:REFERENCE_FOR]->(study)
    WHERE NOT reference.id IN $reference_ids
  DELETE reference_for
}
OPTIONAL CALL (study) {
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  MERGE (reference)-[reference_for:REFERENCE_FOR]->(study)
}
//Update design (in ontology)
CALL (study) {
  OPTIONAL MATCH (study)-[has_design:USES_DESIGN]->(design:Design)
    WHERE NOT design.id = $design_id
  DELETE has_design
}
OPTIONAL CALL (study) {
  MATCH (design: Design {id :$design_id})
  MERGE (study)-[:USES_DESIGN]->(design)
}
//Update licence (reference)
CALL (study) {
  OPTIONAL MATCH (study)-[uses_licence:USES_LICENCE]->(licence:Reference)
    WHERE NOT licence.id = $licence_id
  DELETE uses_licence
}
OPTIONAL CALL (study) {
  MATCH (licence: Reference {id: $licence_id})
  MERGE (study)-[:USES_LICENCE]->(licence)
}
RETURN null
