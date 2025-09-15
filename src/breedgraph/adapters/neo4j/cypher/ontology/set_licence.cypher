MATCH (version: OntologyVersion {id: $version_id})
OPTIONAL MATCH (version)-[l:USES_LICENCE]->(:Reference)
DELETE l
WITH version
MATCH (licence:Reference {id: $licence_id})
CREATE (version)-[:USES_LICENCE]-(licence)
