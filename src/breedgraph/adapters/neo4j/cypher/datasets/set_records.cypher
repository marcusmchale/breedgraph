UNWIND range(0, size($records)-1) as cnt
WITH cnt, $records[cnt] AS record_data
ORDER BY cnt
  MATCH (record:Record {id: record_data['id']})<-[:INCLUDES_RECORD]-(:Dataset)-[:FOR_STUDY]->(study:Study)
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
  CALL (record_data, record)  {
    OPTIONAL MATCH (record)-[for_unit:FOR_UNIT]->(unit:Unit)
    WHERE NOT unit.id = record_data['unit']
    DELETE for_unit
  }
  CALL (record_data, record)  {
    MATCH (unit:Unit {id: record_data['unit']})
    MERGE (record)-[:FOR_UNIT]->(unit)
  }
  // Update references
  CALL (record_data, record) {
    OPTIONAL MATCH (record)<-[reference_for:REFERENCE_FOR]-(reference:Reference)
    WHERE NOT reference.id in record_data['references']
    DELETE reference_for
  }
  OPTIONAL CALL (record_data, record)  {
    MATCH (reference: Reference) WHERE reference.id in record_data['references']
    MERGE (reference)-[ref_for:REFERENCE_FOR]->(record)
  }
  // Update grouping
  CALL (record) {
    OPTIONAL MATCH (record)-[group_rel:IN_GROUP]->(:RecordGroup)
    DELETE group_rel
  }
  OPTIONAL CALL (study, record, record_data) {
    UNWIND record_data.groups AS group_data
    MATCH (study)-[:USES_GROUPING]->(grouping:RecordGrouping {name: group_data.name})
    MERGE (grouping)-[:HAS_GROUP]->(group:RecordGroup {code: group_data.code})
    MERGE (record)-[:IN_GROUP]->(group)
    WITH collect({
      name: grouping.name,
      code: group.code
    }) AS groups
  }

  RETURN NULL