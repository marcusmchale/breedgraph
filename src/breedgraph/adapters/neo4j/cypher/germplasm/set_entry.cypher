MATCH (entry: Germplasm {id: $entry_id})
SET entry += $props
WITH entry
// Link methods
CALL (entry) {
  MATCH (entry)-[uses_method:USES_CONTROL_METHOD ]->(method:ControlMethod)
    WHERE NOT method.id IN $control_methods
  DELETE uses_method
}
CALL (entry) {
  MATCH (method:ControlMethod) WHERE method.id IN $control_methods
  MERGE (entry)-[uses_method:USES_CONTROL_METHOD]->(method)
  ON CREATE SET uses_method.time = datetime.transaction()
}
// Link references
CALL (entry) {
  MATCH (entry)<-[ref_for:REFERENCE_FOR]-(reference:Reference)
    WHERE NOT reference.id IN $references
  DELETE ref_for
}
CALL (entry) {
  MATCH (reference:Reference) WHERE reference.id IN $references
  MERGE (entry)<-[ref_for:REFERENCE_FOR]-(reference)
  ON CREATE SET ref_for.time = datetime.transaction()
}
// Link the unit it came from
CALL (entry) {
  MATCH (entry)-[from_unit:FROM_UNIT]->(unit:Unit)
    WHERE $unit IS NULL OR NOT unit.id = $unit
  DELETE from_unit
}
CALL (entry) {
  MATCH (unit:Unit {id: $unit})
  MERGE (entry)-[from_unit:FROM_UNIT]->(unit)
  ON CREATE SET from_unit.time = datetime.transaction()
}
RETURN NULL