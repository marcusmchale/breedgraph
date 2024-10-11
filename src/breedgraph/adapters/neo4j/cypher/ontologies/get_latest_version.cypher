MATCH (version:OntologyVersion)
RETURN version {.*}
ORDER BY version.id DESCENDING
LIMIT 1
