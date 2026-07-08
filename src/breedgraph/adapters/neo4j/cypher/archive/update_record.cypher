MATCH (record: FileArchiveRecord {file_id: $file_id})
SET record += $updates
RETURN record { .* }