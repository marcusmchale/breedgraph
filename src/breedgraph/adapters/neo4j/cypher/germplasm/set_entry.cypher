MATCH (entry: GermplasmEntry {id: $id})
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
  MATCH (entry)-[uses_method:USES_METHOD ]->(method: GermplasmMethod)
  WHERE NOT method.id in $methods
  DELETE uses_method
  WITH DISTINCT entry
  MATCH (method:GermplasmMethod) WHERE method.id in $methods
  MERGE (entry)-[uses_method:USES_METHOD]->(method)
  ON CREATE SET uses_method.time = datetime.transaction()
  RETURN
    collect(method.id) AS methods
}
// Link references
CALL {
  WITH entry
  MATCH (entry)<-[ref_for:REFERENCE_FOR]->(reference: Reference)
  WHERE NOT reference.id in $references
  DELETE ref_for
  WITH DISTINCT entry
  MATCH (reference:Reference) WHERE reference.id in $references
  MERGE (entry)<-[ref_for:REFERENCE_FOR]->(reference)
  ON CREATE SET ref_for.time = datetime.transaction()
  RETURN
    collect(reference.id) AS references
}
RETURN entry {
       .*,
         methods: methods,
         references:references
     }
