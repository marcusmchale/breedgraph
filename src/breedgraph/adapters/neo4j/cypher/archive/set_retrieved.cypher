MATCH (record: FileArchiveRecord {
  file_id: $file_id,
  file_hash: $file_hash
})
// retrieved for use, so its local copy is kept as long as after a download (get_expired_local_records)
SET record.archive_state = "archived", record.local_state = "local", record.last_accessed = datetime.transaction()
RETURN record { .* }