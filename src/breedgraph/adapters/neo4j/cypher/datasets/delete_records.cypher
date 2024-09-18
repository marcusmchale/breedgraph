MATCH (r:Record) WHERE r.id in $record_ids
DETACH DELETE r