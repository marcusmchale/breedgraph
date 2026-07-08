MATCH (record: FileArchiveRecord {file_id: $file_id})
DETACH DELETE record