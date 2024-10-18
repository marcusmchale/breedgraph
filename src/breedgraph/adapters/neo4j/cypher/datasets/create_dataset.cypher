MERGE (counter: Counter {name: 'dataset'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (dataset: DataSet {id: counter.count})
WITH
  dataset
//Link Term
CALL{
  WITH dataset
  MATCH (term: Variable|EventType|Parameter {id: $term})
  CREATE (dataset)-[for_term:FOR_TERM]->(term)
  RETURN
    collect(term.id)[0] AS term
}
//Link contributors
CALL{
  WITH dataset
  MATCH (contributor: Person) WHERE contributor.id IN $contributors
  CREATE (contributor)-[contributed:CONTRIBUTED_TO]->(dataset)
  RETURN
    collect(contributor.id) AS contributors
}
//Link references
CALL{
  WITH dataset
  MATCH (reference: Reference) WHERE reference.id IN $references
  CREATE (reference)-[reference_for: REFERENCE_FOR]->(dataset)
  RETURN
    collect(reference.id) AS references
}
// Create records
CALL {
  WITH dataset
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
      submitted: datetime.transaction(),
      value:record_data['value'],
      start:datetime(record_data['start']['str']),
      start_unit:record_data['start']['unit'],
      start_step:record_data['start']['step'],
      end:datetime(record_data['end']['str']),
      end_unit:record_data['end']['unit'],
      end_step:record_data['end']['step']
    })-[:FOR_UNIT]->(unit)
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
    term: term,
    records: records,
    contributors: contributors,
    references: references
  }