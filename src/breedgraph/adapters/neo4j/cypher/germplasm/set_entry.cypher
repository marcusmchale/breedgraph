MATCH (entry: Germplasm {id: $entry_id})
SET entry += $props
WITH entry
// Link methods
CALL {
  WITH entry
  MATCH (entry)-[uses_method:USES_CONTROL_METHOD ]->(method:ControlMethod)
    WHERE NOT method.id IN $control_methods
  DELETE uses_method
}
CALL {
  WITH entry
  MATCH (method:ControlMethod) WHERE method.id IN $control_methods
  MERGE (entry)-[uses_method:USES_CONTROL_METHOD]->(method)
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