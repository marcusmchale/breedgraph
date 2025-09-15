MATCH (: Germplasm {id: $entry_id})-[:SOURCE_FOR*]->(descendant: Germplasm)
RETURN descendant.id
