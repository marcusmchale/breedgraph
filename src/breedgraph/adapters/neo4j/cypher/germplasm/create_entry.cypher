MERGE (counter: Counter {name: 'germplasm'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (entry: Germplasm {
  id:counter.count
})
SET entry += $params

WITH entry
// Link methods
CALL (entry) {
  UNWIND $control_methods AS method_id
  MATCH (method: ControlMethod {id: method_id})
  CREATE (entry)-[uses_method:USES_CONTROL_METHOD {time:datetime.transaction()}]->(method)
  RETURN
    collect(method.id) AS control_methods
}
// Link references
CALL (entry) {
  UNWIND $references AS ref_id
  MATCH (reference: Reference {id: ref_id})
  CREATE (reference)-[ref_for:REFERENCE_FOR {time:datetime.transaction()}]->(entry)
  RETURN
    collect(reference.id) AS references
}
// Link the unit it came from (optional)
CALL (entry) {
  MATCH (unit: Unit {id: $unit})
  CREATE (entry)-[from_unit:FROM_UNIT {time:datetime.transaction()}]->(unit)
  RETURN
    collect(unit.id)[0] AS unit
}
RETURN entry {
       .*,
         control_methods: control_methods,
         references:references,
         unit: unit
     }
