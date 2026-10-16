MATCH (record: FileArchiveRecord {file_id: $file_id})
OPTIONAL MATCH (:ArchiveRequests)-[requested:REQUESTED_RETRIEVAL]->(record)
WITH record, min(requested.time) AS retrieval_requested_at
RETURN record { .*, retrieval_requested_at: retrieval_requested_at }
