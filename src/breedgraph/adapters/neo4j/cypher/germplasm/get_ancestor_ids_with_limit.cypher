MATCH (: Germplasm {id: $entry_id})<-[:SOURCE_FOR*..$limit]-(ancestor: Germplasm)
RETURN ancestor.id
