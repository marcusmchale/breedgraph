MERGE (counter: Counter {name: 'ontology_version'})
ON CREATE SET counter.count = 0
SET counter.count = counter.count +1

CREATE (version: OntologyVersion {
  id: ontologies.count,
  major: $major,
  minor: $minor,
  patch: $patch,
  comment: $comment,
  time:timestamp()
})
RETURN version {.*}
