MATCH (record: FileArchiveRecord {
  file_id: $file_id,
  file_hash: $file_hash
})
SET record.archive_state = "RETRIEVED"
RETURN record { .* }