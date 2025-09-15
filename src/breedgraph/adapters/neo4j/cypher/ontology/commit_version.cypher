OPTIONAL MATCH (latest_commit:OntologyCommit)
WITH latest_commit
ORDER BY latest_commit.id DESC
LIMIT 1
CREATE (commit: OntologyCommit {
  version: $version,
  comment: $comment
})
WITH latest_commit, commit
OPTIONAL CALL (latest_commit, commit) {
  WITH commit, latest_commit WHERE latest_commit IS NOT NULL
  CREATE (latest_commit)-[:PRECEDES_COMMIT]->(commit)
}
WITH commit
CALL (commit) {
  MATCH (user: User {id: $user_id})
  MERGE (user)-[:COMMITTED]->(commits:UserOntologyCommits)
  CREATE (commits)-[committed:COMMITTED {time:datetime.transaction()}]->(commit)
  RETURN user.id as user_id
}
OPTIONAL CALL (commit) {
  MATCH (licence: Reference {id: $licence})
  CREATE (commit)-[:USES_LICENCE]->(licence)
  RETURN licence.id as licence
}
OPTIONAL CALL (commit) {
  MATCH (copyright: Reference {id: $copyright})
  CREATE (commit)-[:USES_COPYRIGHT]->(copyright)
  RETURN copyright.id as copyright
}
RETURN commit {
  .*,
  licence: licence,
  copyright: copyright
}
