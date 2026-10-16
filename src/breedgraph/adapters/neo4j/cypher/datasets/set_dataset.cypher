MATCH
  (dataset: Dataset {id: $id})
WITH dataset
//Update study
CALL (dataset) {
  OPTIONAL MATCH (dataset)-[for_study:FOR_STUDY]->(study: Study)
  WHERE NOT study.id = $study
  DELETE for_study
}
CALL (dataset) {
  MATCH (study: Study {id: $study})
  MERGE (dataset)-[:FOR_STUDY]->(study)
}
//Update concept
CALL (dataset) {
  OPTIONAL MATCH (dataset)-[for_concept:FOR_CONCEPT]->(concept: Variable|Factor)
  WHERE NOT dataset.id = $concept
  DELETE for_concept
}
CALL (dataset) {
  MATCH (concept: Variable|Factor {id: $concept})
  MERGE (dataset)-[:FOR_CONCEPT]->(concept)
}
//Update contributions
CALL (dataset) {
  OPTIONAL MATCH (person: Person)-[contributed:CONTRIBUTED_TO]->(dataset)
  WHERE NOT person.id IN [contribution IN $contributions | contribution.person]
  DELETE contributed
}
OPTIONAL CALL (dataset) {
  UNWIND $contributions AS contribution
  MATCH (person: Person {id: contribution.person})
  MERGE (person)-[contributed:CONTRIBUTED_TO]->(dataset)
  SET contributed.roles = contribution.roles
}
//Update references
CALL (dataset) {
  OPTIONAL MATCH (reference: Reference)-[reference_for:REFERENCE_FOR]->(dataset)
  WHERE NOT reference.id in $references
  DELETE reference_for
}
OPTIONAL CALL (dataset) {
  MATCH (reference: Reference) WHERE reference.id in $references
  MERGE (reference)-[ref_for:REFERENCE_FOR]->(dataset)
}

RETURN NULL
