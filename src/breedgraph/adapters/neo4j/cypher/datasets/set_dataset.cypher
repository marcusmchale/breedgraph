MATCH
  (dataset: DataSet {id: $id})
WITH dataset
//Update Term
CALL{
  WITH dataset
  MATCH (dataset)-[for_term:FOR_TERM]->(term: Variable|EventType|Parameter)
  WHERE NOT term.id = $term
  DELETE for_term
}
CALL{
  WITH dataset
  MATCH (term: Variable|EventType|Parameter {id: $term})
  MERGE (dataset)-[:FOR_TERM]->(term)
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
