MATCH (record: FileArchiveRecord {file_id: $file_id})
SET record += $updates
SET record.last_attempt_at = datetime.transaction()
RETURN record { .* }
