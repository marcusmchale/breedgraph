MATCH (version: OntologyVersion {id: $version_id})
OPTIONAL MATCH (version)<-[l:LICENCE_FOR]-()
DELETE l
WITH version
MATCH (licence:LegalReference {id: $licence_id})
CREATE (version)<-[:LICENCE_FOR]-(licence)
