MATCH (dataset: DataSet {id: $dataset_id})
MERGE (record_counter: count {name: 'record'})
ON CREATE SET record_counter.count = 0
WITH dataset, record_counter
UNWIND $unit_records AS unit_record
  MATCH (unit:Unit {id:unit_record[0]})
  UNWIND unit_record[1] AS record_data
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
    WITH unit, record_data, record
    OPTIONAL MATCH (reference:Reference) WHERE reference.id IN record_data['references']
    FOREACH( i IN CASE WHEN reference IS NOT NULL THEN [1] ELSE [] END |
      CREATE (reference)-[:REFERENCE_FOR]->(record)
    )
    WITH unit, record, [reference IN collect(reference) | reference.id] AS references
RETURN unit.id as unit_id, collect(record {.*, references:references}) AS records

