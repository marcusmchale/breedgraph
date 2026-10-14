// A page of a dataset's records in submission order, optionally narrowed to units and a time window.
// Units narrow to the records of the given units and of every unit below them, so a block or a plot selects
// what it contains. A record is in the window when its own period (start to end, either standing in for a
// missing other) overlaps it. The caller has checked that the dataset is readable.
MATCH (dataset:Dataset {id: $dataset_id})
CALL () {
  UNWIND coalesce($unit_ids, []) AS selected_id
  MATCH (selected:Unit {id: selected_id})-[:INCLUDES_UNIT*0..]->(descendant:Unit)
  RETURN collect(DISTINCT descendant.id) AS selected_units
}
MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
WHERE ($unit_ids IS NULL OR unit.id IN selected_units)
  AND ($start IS NULL OR coalesce(record.end, record.start) >= $start)
  AND ($end IS NULL OR coalesce(record.start, record.end) <= $end)
WITH record, unit
ORDER BY record.submitted, record.id
SKIP $offset
LIMIT $limit
RETURN record {
  .*,
  unit: unit.id,
  references: [(record)<-[:REFERENCE_FOR]-(reference:Reference) | reference.id],
  groups: [
    (record)-[:IN_GROUP]->(group:RecordGroup)<-[:HAS_GROUP]-(grouping:RecordGrouping) |
    { id: grouping.id, code: group.code }
  ]
} AS record
