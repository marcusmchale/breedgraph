MATCH (version: OntologyVersion {id: $version_id})
OPTIONAL MATCH (version)<-[l:COPYRIGHT_FOR]-()
DELETE l
WITH version
MATCH (copyright: LegalReference {id: $copyright_id})
CREATE (version)<-[:COPYRIGHT_FOR]-(copyright)