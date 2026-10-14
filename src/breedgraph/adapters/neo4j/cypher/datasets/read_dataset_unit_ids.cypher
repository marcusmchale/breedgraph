// The ids of the units a dataset has records for, in id order, narrowed to units and a time window the same way
// as read_dataset_records, so a client can page through records by unit and keep every unit's records together.
// The caller has checked that the dataset is readable.
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
WITH DISTINCT unit.id AS unit_id
ORDER BY unit_id
RETURN collect(unit_id) AS unit_ids
