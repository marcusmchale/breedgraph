// The licence a new version keeps when it names none: the latest version's or, where it has none, the standard licence
// seeded with the key $default_seed_key (CC BY 4.0), which the first version takes when seeded
OPTIONAL CALL () {
  MATCH (commit:OntologyCommit)
  WITH commit
  ORDER BY commit.version DESCENDING
  LIMIT 1
  MATCH (commit)-[:USES_LICENCE]->(licence:Reference)
  RETURN licence.id AS latest
}
OPTIONAL MATCH (standard:Reference {seed_key: $default_seed_key})
RETURN coalesce(latest, standard.id) AS licence
