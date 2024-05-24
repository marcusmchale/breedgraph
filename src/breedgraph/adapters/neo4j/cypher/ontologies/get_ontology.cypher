MATCH (version:OntologyVersion {id: $version_id})
OPTIONAL MATCH
  (version)<-[:IN_VERSION]-(entry: OntologyEntry)
WITH
  version,
  entry {
    .*,
    labels: labels(entry),
    parents: [(entry)-[:CHILD_OF]->(e:OntologyEntry) |e.id],
    children: [(entry)<-[:CHILD_OF]-(e:OntologyEntry) |e.id],
    authors: [(entry)<-[:AUTHORED]-(p:Person)|p.id],
    references: [(entry)<-[:REFERENCE_FOR]-(r:Reference)|r.id],
    subjects: [(entry)-[:OF_SUBJECT]->(s:Subject) |s.id],
    trait: [(entry)<-[:DESCRIBED_BY]-(t:Trait) | t.id][0],
    condition: [(entry)<-[:DESCRIBED_BY]-(c:Condition) | c.id][0],
    exposure: [(entry)<-[:DESCRIBED_BY]-(e:Exposure) | e.id][0],
    method: [(entry)<-[:METHOD_OF]-(m:Method) | m.id][0],
    scale: [(entry)<-[:SCALE_OF]-(s:Scale) | s.id][0],
    categories: [(entry)<-[:CATEGORY_OF]-(c:Category) | c.id]
  } as entry

RETURN
  version {.*},
  collect(entry) as entries

