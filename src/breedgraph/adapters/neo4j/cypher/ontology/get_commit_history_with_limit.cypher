MATCH (commit:OntologyCommit)<-[committed:COMMITTED]-(:UserOntologyCommits)<-[:COMMITTED]-(user:User)
RETURN commit {
       . *,
         time:committed.time,
         user:user.id,
         licence: [(ontology_commit)-[:USES_LICENCE]->(licence:Reference) | licence.id][0],
         copyright: [(ontology_commit)-[:USES_COPYRIGHT]->(copyright:Reference) | copyright.id][0]
       }
ORDER BY commit.version
LIMIT $limit