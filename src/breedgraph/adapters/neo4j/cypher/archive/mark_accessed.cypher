MATCH (record: FileArchiveRecord {file_id: $file_id})
SET record.last_accessed = datetime.transaction()