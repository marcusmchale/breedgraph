// Remove groupings, but only when there are no record groups formed already.
MATCH (grouping: RecordGrouping) WHERE grouping.id in $grouping_ids
OPTIONAL MATCH (grouping)-[:HAS_GROUP]->(group:RecordGroup)
WITH grouping WHERE group IS NULL
DETACH DELETE grouping