MATCH (source:Germplasm)-[relationship:SOURCE_FOR]->(target:Germplasm {id: $entry_id})
RETURN
  source.id as source_id,
  target.id as target_id,
  relationship.source_type as source_type,
  relationship.description as description