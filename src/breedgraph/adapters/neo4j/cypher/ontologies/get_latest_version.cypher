MATCH (version:OntologyVersion)
WITH version
ORDER BY version.id DESCENDING
LIMIT 1
RETURN
  version {.*}