MATCH (user: User {id: $user_id})
    -[:REQUESTED_RETRIEVAL]->(requests:ArchiveRequests)
    -[:REQUESTED_RETRIEVAL]->(record: FileArchiveRecord {file_id: $file_id})
RETURN user {
  .id,
  .fullname,
  .email
} as requestor
