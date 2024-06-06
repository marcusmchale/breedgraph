MATCH (version: OntologyVersion {id: $version_id})
CALL apoc.refactor.cloneNodes([version], TRUE)
YIELD output
MATCH (counter: Counter {name: 'ontology_version'})
SET counter.count = counter.count + 1
SET output += {
  id: counter.count,
  major: $major,
  minor: $minor,
  patch: $patch,
  comment: $comment,
  time:timestamp()
}
RETURN output {.*} as version
