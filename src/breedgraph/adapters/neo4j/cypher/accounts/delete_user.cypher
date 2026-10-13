// Tombstone a deleted account. The node is kept, relabelled DeletedUser, so that provenance
// (contributions, ontology commits and lifecycle changes) stays attributed to an anonymous id.
// Relabelling also excludes it from every query matching :User, so login tokens no longer resolve.
MATCH (user: User {id: $user_id})
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
SET user = {id: user.id, deleted_at: datetime.transaction()}
