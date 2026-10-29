// Tombstone deleted accounts. The node is kept, relabelled DeletedUser, so that provenance
// (contributions, ontology commits and lifecycle changes) stays attributed to an anonymous id.
// Relabelling also excludes it from every query matching :User, so login tokens no longer resolve.
// Also used to apply logged deletions again after restoring a backup taken before them;
// accounts already deleted, or not in the backup, are skipped. Where the creation time is logged,
// only the account created then is deleted, never another given its id after a restore rolled the id counter back.
UNWIND $deletions AS deletion
MATCH (user: User {id: deletion.user_id})
WHERE deletion.created_at IS NULL OR user.time.epochMillis = datetime(deletion.created_at).epochMillis
// An agreement to be listed among the ontology's contributors is the account's, so it goes with the link
CALL (user) {
  MATCH (user)-[:IS_PERSON]->(person: Person)
  REMOVE person.ontology_credit
}
CALL (user) {
  MATCH (user)-[r: READ|WRITE|CURATE|ADMIN|IS_PERSON|CLAIMS]->()
  DELETE r
}
// Pending invitations hold other people's email addresses and offer the user's own authority
CALL (user) {
  MATCH (user)-[:INVITED]->(invitation: Invitation)
  DETACH DELETE invitation
}
// Requests to restore archived files are kept only to notify the requestor
CALL (user) {
  MATCH (user)-[:REQUESTED_RETRIEVAL]->(requests: ArchiveRequests)
  DETACH DELETE requests
}
REMOVE user: User
SET user: DeletedUser
SET user = {id: user.id, deleted_at: datetime(deletion.deleted_at)}
RETURN count(user) AS deleted
