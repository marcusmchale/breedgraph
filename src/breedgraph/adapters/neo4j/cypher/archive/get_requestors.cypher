// Everyone who asked for the file to be retrieved from the archive
MATCH (user: User)
    -[:REQUESTED_RETRIEVAL]->(:ArchiveRequests)
    -[:REQUESTED_RETRIEVAL]->(:FileArchiveRecord {file_id: $file_id})
RETURN user {
  .id,
  .fullname,
  .email
} as requestor
