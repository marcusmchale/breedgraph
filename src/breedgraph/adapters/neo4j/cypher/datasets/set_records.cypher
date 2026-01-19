UNWIND range(0, size($records)-1) as cnt
WITH cnt, $records[cnt] AS record_data
ORDER BY cnt
  MATCH (record:Record {id: record_data['id']})
  SET
    record.value = record_data['value'],
    record.start = record_data['start'],
    record.start_unit = record_data['start_unit'],
    record.start_step = record_data['start_step'],
    record.end = record_data['end'],
    record.end_unit = record_data['end_unit'],
    record.end_step = record_data['end_step']
  WITH record_data, record
  //Update Unit
  CALL {
    WITH record_data, record
    MATCH (record)-[for_unit:FOR_UNIT]->(unit:Unit)
    WHERE NOT unit.id = record_data['unit']
    DELETE for_unit
  }
  CALL {
    WITH record_data, record
    MATCH (unit:Unit {id: record_data['unit']})
    MERGE (record)-[:RECORD_FOR]->(unit)
  }
  // Update references
  CALL {
    WITH record_data, record
    MATCH (record)<-[reference_for:REFERENCE_FOR]-(reference:Reference)
    WHERE NOT reference.id in record_data['references']
    DELETE reference_for
  }
  CALL {
    WITH record_data, record
    MATCH (reference: Reference)
    WHERE reference.id in record_data['references']
    MERGE (reference)-[ref_for:REFERENCE_FOR]->(record)
  }
  RETURN NULL