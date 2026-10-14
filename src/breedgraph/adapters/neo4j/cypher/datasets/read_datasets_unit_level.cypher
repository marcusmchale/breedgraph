// One level of the units some datasets have records for, under a narrowing by time: the children of the given
// parents that have records at or below them, or, with no parents, the roots of the blocks that do. Each comes with
// how many units at or below it have records, how many records that is, and whether any of those units lies below
// it, so a client can offer a tree of only the units that matter to the datasets, level by level.
// The caller has kept only the datasets the user can read; units are not redacted here, the units view does that.
CALL () {
  WITH 1 AS _
  WHERE $parent_ids IS NULL
  UNWIND $dataset_ids AS dataset_id
  MATCH (:Dataset {id: dataset_id})-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
  WHERE ($start IS NULL OR coalesce(record.end, record.start) >= $start)
    AND ($end IS NULL OR coalesce(record.start, record.end) <= $end)
  WITH DISTINCT unit
  MATCH (root:Unit)-[:INCLUDES_UNIT*0..]->(unit)
  WHERE NOT (:Unit)-[:INCLUDES_UNIT]->(root)
  RETURN DISTINCT root AS child
  UNION
  WITH 1 AS _
  WHERE $parent_ids IS NOT NULL
  UNWIND $parent_ids AS parent_id
  MATCH (:Unit {id: parent_id})-[:INCLUDES_UNIT]->(child:Unit)
  RETURN DISTINCT child
}
MATCH (child)-[:INCLUDES_UNIT*0..]->(unit:Unit)<-[:FOR_UNIT]-(record:Record)<-[:INCLUDES_RECORD]-(dataset:Dataset)
WHERE dataset.id IN $dataset_ids
  AND ($start IS NULL OR coalesce(record.end, record.start) >= $start)
  AND ($end IS NULL OR coalesce(record.start, record.end) <= $end)
WITH child,
  count(DISTINCT unit) AS unit_count,
  count(DISTINCT record) AS record_count,
  max(CASE WHEN unit = child THEN 0 ELSE 1 END) AS below
RETURN child.id AS id, unit_count, record_count, below = 1 AS has_children
ORDER BY child.name, child.id
