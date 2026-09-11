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

//Update groupings
/// First delete removed groupings
CALL (study) {
  WITH [grouping IN $groupings | grouping.name] AS group_names
  OPTIONAL MATCH (study)-[:USES_GROUPING]->(grouping:RecordGrouping) WHERE NOT grouping.name IN group_names
  OPTIONAL MATCH (grouping)-[:HAS_SCOPE]->(scope: GroupingScope)
  DETACH DELETE scope, grouping
}
// Then merge to create or update groupings
OPTIONAL CALL (study) {
  UNWIND $groupings AS grouping_data
  MERGE (study)-[:USES_GROUPING]->(grouping: RecordGrouping { name:grouping_data.name })
  WITH grouping, grouping_data
  OPTIONAL CALL (grouping, grouping_data) {
    // Delete all scopes
    OPTIONAL MATCH (grouping)-[:HAS_SCOPE]->(scope:GroupingScope)
    DETACH DELETE scope
    UNWIND grouping_data.scopes as scope_data
      // Then create each scope anew
      CREATE (grouping)-[:HAS_SCOPE]->(scope: GroupingScope)
      WITH scope, scope_data
      MATCH (dataset: Dataset) WHERE dataset.id IN scope_data.dataset_ids
      CREATE (scope)<-[:IN_SCOPE]-(dataset)
      WITH scope, collect(dataset.id) as dataset_ids
}

RETURN null
