MATCH (: Germplasm {id: $entry_id})-[:SOURCE_FOR*..$limit]->(descendant: Germplasm)
RETURN descendant.id