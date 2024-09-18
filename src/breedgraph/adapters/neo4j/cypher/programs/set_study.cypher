MATCH
  (study: Study {id: $id})
SET
  study.name = $name,
  study.fullname = $fullname,
  study.description = $description,
  study.external_id = $external_id,
  study.practices = $practices,
  study.start = datetime($start['str']),
  study.start_unit = datetime($start['unit']),
  study.start_step = datetime($start['step']),
  study.end = datetime($end['str']),
  study.end_unit = datetime($end['unit']),
  study.end_step = datetime($end['step'])
WITH study
// Update references
CALL {
  WITH study
  MATCH (reference:Reference)-[reference_for:REFERENCE_FOR]->(study)
    WHERE NOT reference.id IN $references
  DELETE reference_for
}
CALL {
  WITH study
  MATCH (reference: Reference) WHERE reference.id IN $references
  MERGE (reference)-[reference_for:REFERENCE_FOR]->(study)
}
// Update factors (DataSet)
CALL {
  WITH study
  MATCH (study)-[has_factor:HAS_FACTOR]->(factor: DataSet) WHERE NOT factor.id IN $factors
  DELETE has_factor
}
CALL {
  WITH study
  MATCH (factor: DataSet) WHERE factor.id IN $factors
  MERGE (study)-[:HAS_FACTOR]->(factor)
}
// Update observations (DataSet)
CALL {
  WITH study
  MATCH (study)-[has_observation:HAS_OBSERVATION]->(observation: DataSet) WHERE NOT observation.id IN $observations
  DELETE has_observation
}
CALL {
  WITH study
  MATCH (observation: DataSet) WHERE observation.id IN $observations
  MERGE (study)-[:HAS_OBSERVATION]->(observation)
}
//Update design (in ontology)
CALL {
  WITH study
  MATCH (study)-[has_design:USES_DESIGN]->(design:Design)
    WHERE NOT design.id = $design
  DELETE has_design
}
CALL {
  WITH study
  MATCH (design: Design {id :$design})
  MERGE (study)-[:USES_DESIGN]->(design)
}
//Update licence (reference)
CALL {
  WITH study
  MATCH (study)-[uses_licence:USES_LICENCE]->(licence:Reference)
    WHERE NOT licence.id = $licence
  DELETE uses_licence
}
CALL {
  WITH study
  MATCH (licence: Reference {id: $licence})
  MERGE (study)-[:USES_LICENCE]->(licence)
}
RETURN NULL
