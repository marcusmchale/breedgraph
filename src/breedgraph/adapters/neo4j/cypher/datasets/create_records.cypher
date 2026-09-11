MATCH (dataset: Dataset {id: $dataset_id})-[:FOR_STUDY]->(study: Study)
MERGE (record_counter: Counter {name: 'record'})
ON CREATE SET record_counter.count = 0
WITH study, dataset, record_counter, record_counter.count as base_id
SET record_counter.count = record_counter.count + size($records)

WITH study, dataset, base_id
UNWIND range(0, size($records)-1) as cnt
WITH study, dataset, cnt, $records[cnt] AS record_data, (base_id + cnt) as next_id
ORDER BY cnt

  MATCH (unit:Unit {id: record_data['unit']})
  CREATE (dataset)-[:INCLUDES_RECORD]->(record:Record {
    id: next_id,
    submitted: datetime.transaction(),
    value:record_data['value'],
    start:record_data['start'],
    start_unit:record_data['start_unit'],
    start_step:record_data['start_step'],
    end:record_data['end'],
    end_unit:record_data['end_unit'],
    end_step:record_data['end_step']
  })-[:FOR_UNIT]->(unit)

  WITH study, dataset, unit, record, record_data

  OPTIONAL CALL (record, record_data) {
    MATCH (reference:Reference) WHERE reference.id IN record_data.references
    CREATE (reference)-[:REFERENCE_FOR]->(record)
    RETURN collect(reference.id) as references
  }

  OPTIONAL CALL (study, record, record_data) {
    UNWIND record_data.groups AS group_data
    MATCH (study)-[:USES_GROUPING]->(grouping:RecordGrouping {name: group_data.name})
    MERGE (grouping)-[:HAS_GROUP]->(group:RecordGroup {code: group_data.code})
    CREATE (record)-[:IN_GROUP]->(group)
    RETURN collect({
      name: grouping.name,
      code: group.code
    }) AS groups
  }

  RETURN record {.*, unit: unit.id, references: references, groups: groups} as record
