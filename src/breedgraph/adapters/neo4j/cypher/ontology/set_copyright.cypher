MATCH (version: OntologyVersion {id: $version_id})
OPTIONAL MATCH (version)-[l:USES_COPYRIGHT]->()
DELETE l
WITH version
MATCH (copyright: Reference {id: $copyright_id})
CREATE (version)-[:USES_COPYRIGHT]-(copyright)