MATCH (: OntologyEntry {id: $entry})-[in_version: IN_VERSION]->(:OntologyVersion {id:$version})
DELETE in_version