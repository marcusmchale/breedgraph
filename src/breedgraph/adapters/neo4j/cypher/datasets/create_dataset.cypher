MERGE (counter: Counter {name: 'dataset'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (dataset: DataSet {id: counter.count})
WITH
  dataset
//Link Ontology Entry
CALL (dataset) {

  MATCH (entry: Variable|EventType|Parameter {id: $ontology_id})
  CREATE (dataset)-[for_term:FOR_ONTOLOGY_ENTRY]->(entry)
  RETURN
    collect(entry.id)[0] AS ontology_id
}
//Link contributors
CALL (dataset) {
  MATCH (contributor: Person) WHERE contributor.id IN $contributors
  CREATE (contributor)-[contributed:CONTRIBUTED_TO]->(dataset)
  RETURN
    collect(contributor.id) AS contributors
}
//Link references
CALL (dataset){
  MATCH (reference: Reference) WHERE reference.id IN $references
  CREATE (reference)-[reference_for: REFERENCE_FOR]->(dataset)
  RETURN
    collect(reference.id) AS references
}
// Create records
CALL (dataset) {
  MERGE (record_counter: Counter {name: 'record'})
  ON CREATE SET record_counter.count = 0
  WITH dataset, record_counter
  UNWIND range(0, size($records)-1) as cnt
  WITH dataset, record_counter, cnt, $records[cnt] AS record_data
  ORDER BY cnt
    MATCH (unit:Unit {id:record_data['unit']})
    SET record_counter.count = record_counter.count + 1
    CREATE (dataset)-[:INCLUDES_RECORD]->(record:Record {
      id: record_counter.count,
      submitted: datetime.transaction()
    })-[:FOR_UNIT]->(unit)
    SET record += record_data
    WITH unit, record, record_data
    OPTIONAL MATCH (reference:Reference) WHERE reference.id IN record_data['references']
    FOREACH( i IN CASE WHEN reference IS NOT NULL THEN [1] ELSE [] END |
      CREATE (reference)-[:REFERENCE_FOR]->(record)
    )
    WITH record {.*, unit: unit.id} as record, [reference IN collect(reference) | reference.id] as references
  RETURN collect(record {.*, references: references}) AS records
}
RETURN
  dataset {
    .*,
    ontology_id: ontology_id,
    records: records,
    contributors: contributors,
    references: references
  }