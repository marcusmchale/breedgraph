MATCH (reference:Reference {file_id: $file_id})
CREATE (record: FileArchiveRecord)-[:FOR_REFERENCE]->(reference)
SET record += $record_data
SET record.last_accessed = datetime.transaction()
RETURN record { .* }
