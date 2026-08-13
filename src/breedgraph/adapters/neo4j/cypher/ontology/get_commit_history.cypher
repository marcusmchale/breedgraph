MATCH (commit:OntologyCommit)<-[committed:COMMITTED]-(:UserOntologyCommits)<-[:COMMITTED]-(user:User)
RETURN commit {
       . *,
         time:committed.time,
         user:user.id,
         licence: [(commit)-[:USES_LICENCE]->(licence:Reference) | licence.id][0],
         copyright: [(commit)-[:USES_COPYRIGHT]->(copyright:Reference) | copyright.id][0]
       }
ORDER BY commit.version DESC