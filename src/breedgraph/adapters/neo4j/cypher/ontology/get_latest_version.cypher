MATCH (version:OntologyCommit)
RETURN version {.*}
ORDER BY version.id DESCENDING
LIMIT 1
