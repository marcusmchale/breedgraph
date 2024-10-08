MATCH (entry: Germplasm {id: $id})
SET
  entry.name = $name,
  entry.synonyms = $synonyms,
  entry.description =  $description,
  entry.reproduction = $reproduction,
  entry.time = datetime($time['str']),
  entry.time_unit = $time['unit'],
  entry.time_step = $time['step']
WITH entry
// Link methods
CALL {
  WITH entry
  MATCH (entry)-[uses_method:USES_METHOD ]->(method:GermplasmMethod)
    WHERE NOT method.id IN $methods
  DELETE uses_method
}
CALL {
  WITH entry
  MATCH (method:GermplasmMethod) WHERE method.id IN $methods
  MERGE (entry)-[uses_method:USES_METHOD]->(method)
  ON CREATE SET uses_method.time = datetime.transaction()
}
// Link references
CALL {
  WITH entry
  MATCH (entry)<-[ref_for:REFERENCE_FOR]->(reference:Reference)
    WHERE NOT reference.id IN $references
  DELETE ref_for
}
CALL {
  WITH entry
  MATCH (reference:Reference) WHERE reference.id IN $references
  MERGE (entry)<-[ref_for:REFERENCE_FOR]->(reference)
  ON CREATE SET ref_for.time = datetime.transaction()
}
RETURN NULL