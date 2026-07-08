MATCH (record: FileArchiveRecord)
WHERE record.archive_state IN $archive_states
RETURN record { .* }
ORDER BY record.last_attempt_at ASC