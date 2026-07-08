MATCH (:ArchiveRequests)-[requests:REQUESTED_RETRIEVAL]->(: FileArchiveRecord {file_id: $file_id})
DELETE requests