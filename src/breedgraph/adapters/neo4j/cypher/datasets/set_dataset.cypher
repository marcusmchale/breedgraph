MATCH
  (dataset: DataSet {id: $id})
WITH dataset
//Update concept
CALL{
  WITH dataset
  MATCH (dataset)-[for_concept:FOR_CONCEPT]->(concept: Variable|Factor)
  WHERE NOT dataset.id = $concept
  DELETE for_concept
}
CALL{
  WITH dataset
  MATCH (concept: Variable|Factor {id: $concept})
  MERGE (dataset)-[:FOR_CONCEPT]->(concept)
}
//Update contributors
CALL{
  WITH dataset
  MATCH (contributor: Person)-[contributed:CONTRIBUTED_TO]->(dataset)
  WHERE NOT contributor.id in $contributors
  DELETE contributed
}
CALL{
  WITH dataset
  MATCH (contributor: Person) WHERE contributor.id in $contributors
  MERGE (contributor)-[:CONTRIBUTED_TO]->(dataset)
}
//Update references
CALL{
  WITH dataset
  MATCH (reference: Reference)-[reference_for:REFERENCE_FOR]->(dataset)
  WHERE NOT reference.id in $references
  DELETE reference_for
}
CALL{
  WITH dataset
  MATCH (reference: Reference) WHERE reference.id in $references
  MERGE (reference)-[:REFERENCE_FOR]->(dataset)
}
RETURN NULL
