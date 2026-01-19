MATCH
  (dataset: Dataset {id: $id})
WITH dataset
//Update study
CALL (dataset) {
  MATCH (study: Study)-[has_dataset:HAS_DATASET]->(dataset)
  WHERE NOT study.id = $study
  DELETE has_dataset
}
CALL (dataset) {
  MATCH (study: Study {id: $study})
  MERGE (study)-[:HAS_DATASET]->(dataset)
}
//Update concept
CALL (dataset) {
  MATCH (dataset)-[for_concept:FOR_CONCEPT]->(concept: Variable|Factor)
  WHERE NOT dataset.id = $concept
  DELETE for_concept
}
CALL (dataset) {
  MATCH (concept: Variable|Factor {id: $concept})
  MERGE (dataset)-[:FOR_CONCEPT]->(concept)
}
//Update contributors
CALL (dataset) {
  MATCH (contributor: Person)-[contributed:CONTRIBUTED_TO]->(dataset)
  WHERE NOT contributor.id in $contributors
  DELETE contributed
}
CALL (dataset) {
  MATCH (contributor: Person) WHERE contributor.id in $contributors
  MERGE (contributor)-[:CONTRIBUTED_TO]->(dataset)
}
//Update references
CALL (dataset) {
  MATCH (reference: Reference)-[reference_for:REFERENCE_FOR]->(dataset)
  WHERE NOT reference.id in $references
  DELETE reference_for
}
CALL (dataset) {
  MATCH (reference: Reference) WHERE reference.id in $references
  MERGE (reference)-[ref_for:REFERENCE_FOR]->(dataset)
}
RETURN NULL
