// The number of a dataset's records, narrowed to units and a time window the same way as read_dataset_records,
// so a client can page through a narrowed set. The caller has checked that the dataset is readable.
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
RETURN count(record) AS record_count
