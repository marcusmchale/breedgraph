MATCH (user: User {id: $user_id})
MERGE (user)-[:REQUESTED_RETRIEVAL]->(requests:ArchiveRequests)
WITH requests
MATCH (record: FileArchiveRecord {file_id: $file_id})
MERGE (requests)-[:REQUESTED_RETRIEVAL {time:datetime.transaction()}]->(record)
SET record.last_accessed = datetime.transaction()