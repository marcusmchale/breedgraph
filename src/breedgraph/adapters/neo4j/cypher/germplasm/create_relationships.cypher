UNWIND $relationships as rel
MATCH (source: Germplasm {id:rel['source_id']})
MATCH (target: Germplasm {id:rel['target_id']})
CREATE (source)-[relationship:SOURCE_FOR {source_type: rel['source_type'], description: rel['description']}]->(target)