MATCH (commit:OntologyCommit)<-[committed:COMMITTED]-(:UserOntologyCommits)<-[:COMMITTED]-(user:User)
WHERE commit.version >= $version_min AND commit.version <= $version_max
RETURN commit {
       . *,
         time:committed.time,
         user:user.id,
         licence: [(ontology_commit)-[:USES_LICENCE]->(licence:Reference) | licence.id][0],
         copyright: [(ontology_commit)-[:USES_COPYRIGHT]->(copyright:Reference) | copyright.id][0]
       }
ORDER BY commit.version