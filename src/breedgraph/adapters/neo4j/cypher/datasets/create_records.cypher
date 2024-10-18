MATCH (dataset: DataSet {id: $dataset_id})
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
  RETURN record {.*, references: references} AS record


