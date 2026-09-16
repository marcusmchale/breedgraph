// Create groupings and scopes
UNWIND $groupings as grouping_data
MATCH (grouping: RecordGrouping {id: grouping_data.id})
SET grouping += { scope: grouping_data.scope, name: grouping_data.name }
WITH grouping, grouping_data

//update type
CALL (grouping, grouping_data) {
  OPTIONAL MATCH (grouping)-[type_rel:OF_TYPE]->(type:RecordGroupType) WHERE type.id <> grouping_data.type
  DELETE type_rel
}

CALL (grouping, grouping_data) {
  MATCH (type: RecordGroupType {id: grouping_data.type})
  MERGE (grouping)-[:OF_TYPE]->(type)
  RETURN type
}

//Update scopes
OPTIONAL CALL (grouping, grouping_data) {
  // Delete all scopes
  OPTIONAL MATCH (grouping)-[:HAS_SCOPE]->(scope:GroupingScope)
  DETACH DELETE scope
  WITH grouping, grouping_data
  UNWIND grouping_data.dataset_scopes as scope_data
    // Then create each scope anew
    CREATE (grouping)-[:HAS_SCOPE]->(scope: GroupingScope)
    WITH scope, scope_data
    MATCH (dataset: Dataset) WHERE dataset.id IN scope_data.dataset_ids
    CREATE (scope)<-[:IN_SCOPE]-(dataset)
    WITH scope, collect(dataset.id) as dataset_ids
  RETURN collect({dataset_ids: dataset_ids}) as scopes
}


RETURN collect({id: grouping.id, name: grouping.name, type: type.id, scope: grouping.scope, scopes: scopes}) as groupings



