MATCH (unit: Unit {id:$id})
SET
  unit.name = $name,
  unit.description = $description
WITH
  unit
// Update subject
CALL (unit) {
  MATCH (unit)-[of_subject:OF_SUBJECT]->(subject:Subject)
    WHERE $subject IS NULL OR NOT subject.id = $subject
  DELETE of_subject
}
CALL (unit) {
  MATCH (subject:Subject {id: $subject})
  MERGE (unit)-[of_subject:OF_SUBJECT]->(subject)
  ON CREATE SET of_subject.time = datetime.transaction()
}

// Update germplasm
CALL (unit) {
  MATCH (unit)-[of_germplasm:OF_GERMPLASM]->(germplasm:Germplasm)
    WHERE $germplasm IS NULL OR NOT germplasm.id = $germplasm
  DELETE of_germplasm
}
CALL (unit) {
  MATCH (germplasm:Germplasm {id: $germplasm})
  MERGE (unit)-[of_germplasm:OF_GERMPLASM]->(germplasm)
  ON CREATE SET of_germplasm.time = datetime.transaction()
}

// Update the units its material came from
CALL (unit) {
  MATCH (unit)-[derived:DERIVED_FROM]->(source:Unit)
    WHERE NOT source.id IN [derivation IN $derived_from | derivation['unit_id']]
  DELETE derived
}
CALL (unit) {
  UNWIND $derived_from AS derivation
  MATCH (source:Unit {id: derivation['unit_id']})
  MERGE (unit)-[derived:DERIVED_FROM]->(source)
  ON CREATE SET derived.time = datetime.transaction()
  SET
    derived.stage = derivation['stage'],
    derived.description = derivation['description']
}

// Positions are not written here but by application.unit_positions: only a new unit's are written with it
RETURN NULL
