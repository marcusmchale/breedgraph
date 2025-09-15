MATCH (entry:Germplasm {id: $entry_id})-[relationship:SOURCE_FOR]-(other:Germplasm)
RETURN
  startNode(relationship).id as source_id,
  endnode(relationship).id as target_id,
  relationship.source_type as source_type,
  relationship.description as description