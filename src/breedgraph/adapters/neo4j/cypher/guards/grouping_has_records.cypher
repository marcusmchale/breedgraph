MATCH (grouping: RecordGrouping {id: $grouping_id})
RETURN EXISTS{
  MATCH (grouping)-[:HAS_GROUP]->(:RecordGroup)<-[:IN_GROUP]-(:Record)
} as in_use
