MERGE (counter: count {name: 'germplasm'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (entry: Germplasm {
  id: counter.count,
  name: $name,
  synonyms: $synonyms,
  description:  $description,
  reproduction: $reproduction,
  time: datetime($time['str']),
  time_unit: $time['unit'],
  time_step: $time['step']
})

WITH entry
// Link methods
CALL {
  WITH entry
  UNWIND $methods as method_id
  MATCH (method: GermplasmMethod {id: method_id})
  CREATE (entry)-[uses_method:USES_METHOD {time:datetime.transaction()}]->(method)
  RETURN
    collect(method.id) AS methods
}
// Link references
CALL {
  WITH entry
  UNWIND $references AS ref_id
  MATCH (reference: Reference {id: ref_id})
  CREATE (reference)-[ref_for:REFERENCE_FOR {time:datetime.transaction()}]->(entry)
  RETURN
    collect(reference.id) AS references
}
RETURN entry {
       .*,
         methods: methods,
         references:references
     }
