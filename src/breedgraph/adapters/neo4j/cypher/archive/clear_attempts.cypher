MATCH (record: FileArchiveRecord {file_id: $file_id})
SET record.attempts = 0, record.last_attempt_at = NULL
