MATCH (: Germplasm {id: $entry_id})<-[:SOURCE_FOR*]-(ancestor: Germplasm)
RETURN ancestor.id
