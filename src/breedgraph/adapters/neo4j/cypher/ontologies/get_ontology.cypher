MATCH (version:OntologyVersion {id: $version_id})
OPTIONAL MATCH
  (version)<-[:IN_VERSION]-(entry: OntologyEntry)
WITH
  version,
  entry {
    .*,
    labels: labels(entry),
    relates_to: [(entry)-[relates_to]->(related:OntologyEntry) | [entry.id, related.id, {relationship:type(relates_to)}]]
    //authors: [(entry)<-[:AUTHORED]-(p:Person)|p.id],
    //references: [(entry)<-[:REFERENCE_FOR]-(r:Reference)|r.id]
} AS entry

RETURN
  version {.*},
  collect(entry) AS entries
