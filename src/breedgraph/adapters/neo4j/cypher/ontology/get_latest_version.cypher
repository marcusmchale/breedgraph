MATCH (commit:OntologyCommit)
RETURN commit.version
ORDER BY commit.version DESCENDING
LIMIT 1
