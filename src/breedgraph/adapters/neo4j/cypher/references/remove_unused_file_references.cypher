// File references found unused (mark_unused_file_references.cypher) more than $days days ago, and not written since
// then: removed, returning their files for deletion
MATCH (reference: Reference)
WHERE reference.unused_since < datetime.transaction() - duration({days: $days})
  AND all(
    time IN [(reference)<-[write:CONTRIBUTED]-(:UserReferences) | write.time]
    WHERE time < datetime.transaction() - duration({days: $days})
  )
WITH reference, reference.file_id AS file_id
DETACH DELETE reference
RETURN file_id
