// Remove groupings with their scopes and record groups. The handler refuses a grouping with records in its groups
// (guards/grouping_has_records), and one that still has them is kept here rather than leave records in no grouping.
// Groups left without records (records lose their codes, or are deleted) go with the grouping
MATCH (grouping: RecordGrouping) WHERE grouping.id in $grouping_ids
  AND NOT EXISTS { MATCH (grouping)-[:HAS_GROUP]->(:RecordGroup)<-[:IN_GROUP]-(:Record) }
CALL (grouping) {
  OPTIONAL MATCH (grouping)-[:HAS_GROUP]->(group:RecordGroup)
  DETACH DELETE group
}
CALL (grouping) {
  OPTIONAL MATCH (grouping)-[:HAS_SCOPE]->(scope:GroupingScope)
  DETACH DELETE scope
}
DETACH DELETE grouping
