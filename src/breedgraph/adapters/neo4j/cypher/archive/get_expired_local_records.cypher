MATCH (record: FileArchiveRecord)
WHERE record.local_state = "local"
AND record.file_size >= $size_limit
AND datetime(record.last_accessed) <= datetime.transaction() - duration({days: $age_limit})

RETURN record { .* }