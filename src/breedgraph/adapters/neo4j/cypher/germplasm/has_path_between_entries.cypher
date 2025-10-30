MATCH path = (:Germplasm {id:$source_id})-[:SOURCE_FOR*]->(:Germplasm {id:$sink_id})
RETURN count(path) > 0 as has_path
LIMIT 1
