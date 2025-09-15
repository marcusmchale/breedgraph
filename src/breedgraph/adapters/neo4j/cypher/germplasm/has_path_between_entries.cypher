MATCH path = (:Germplasm {id:$source_id})-[:SOURCE_FOR*]->(:Germplasm {id:$target_id})
RETURN count(path) > 0 as has_path
LIMIT 1
