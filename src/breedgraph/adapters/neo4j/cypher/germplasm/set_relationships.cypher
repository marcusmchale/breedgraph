UNWIND $relationships as rel
MATCH (: Germplasm {id:rel['source_id']})-[relationship: SOURCE_FOR]->(: Germplasm {id:rel['sink_id']})
SET
  relationship.source_type = rel['source_type'],
  relationship.description = rel['description']