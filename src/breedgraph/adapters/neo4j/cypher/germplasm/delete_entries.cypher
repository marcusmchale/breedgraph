MATCH (entry: Germplasm) where entry.id in $entry_ids
DETACH DELETE (entry)