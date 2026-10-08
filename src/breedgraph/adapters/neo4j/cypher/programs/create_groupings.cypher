// Create groupings and scopes
MATCH (study: Study {id: $study_id})
MERGE (grouping_counter: Counter {name: 'RecordGroup'})
ON CREATE SET grouping_counter.count = 0
WITH study, grouping_counter, grouping_counter.count as base_id
SET grouping_counter.count = grouping_counter.count + size($groupings)

WITH study, base_id
  UNWIND range(0, size($groupings)) as cnt
    WITH study, cnt, $groupings[cnt] as grouping_data, (base_id + cnt) as next_id
    ORDER BY cnt

    MATCH (type: RecordGroupType {id: grouping_data.type})
    CREATE (study)-[:USES_GROUPING]->(grouping:RecordGrouping {
      id: next_id,
      scope: grouping_data.scope,
      name: grouping_data.name
    })-[:OF_TYPE]->(type)
    WITH grouping, grouping_data, type
    OPTIONAL CALL (grouping, grouping_data) {
      UNWIND grouping_data.dataset_scopes AS scope_data
        CREATE (grouping)-[:HAS_SCOPE]->(scope: GroupingScope)
        WITH scope, scope_data
        MATCH (dataset: Dataset) WHERE dataset.id IN scope_data.dataset_ids
        CREATE (scope)<-[:IN_SCOPE]-(dataset)
        WITH scope, collect(dataset.id) as dataset_ids
      RETURN collect({ dataset_ids: dataset_ids }) as scopes
    }

RETURN collect({id: grouping.id, name: grouping.name, type: type.id, scope: grouping.scope, scopes: scopes}) as groupings
