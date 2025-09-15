MATCH
  (dataset: DataSet {id: $id})
WITH dataset
//Update Ontology Entry
CALL{
  WITH dataset
  MATCH (dataset)-[for_entry:FOR_ONTOLOGY_ENTRY]->(entry: Variable|EventType|Parameter)
  WHERE NOT entry.id = $ontology_id
  DELETE for_entry
}
CALL{
  WITH dataset
  MATCH (entry: Variable|EventType|Parameter {id: $ontology_id})
  MERGE (dataset)-[:FOR_ONTOLOGY_ENTRY]->(entry)
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
