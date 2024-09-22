MATCH (version:OntologyVersion {id: $version_id})
OPTIONAL MATCH
  (version)<-[:IN_VERSION]-(entry: OntologyEntry)
WITH
  version,
  entry {
    .*,
    labels: labels(entry),
    relates_to: [
        (entry)-[relates_to]->(related:OntologyEntry)
        WHERE relates_to.created <= version.id AND coalesce(relates_to.removed, Inf) > version.id |
        [entry.id, related.id, {label: type(relates_to), rank: relates_to.rank}]
    ],
    authors: [(entry)<-[:AUTHORED]-(p:Person)|p.id],
    references: [(entry)<-[:REFERENCE_FOR]-(r:Reference)|r.id]
} AS entry

RETURN
  version {.*},
  collect(entry) AS entries
