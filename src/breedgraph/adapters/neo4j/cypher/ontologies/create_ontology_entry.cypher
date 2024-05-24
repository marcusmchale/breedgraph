MATCH (v:OntologyVersion {id: $version_id})
MERGE (c:Counter {name:'ontology_entry'})
ON CREATE SET c.count = 0
SET c.count = c.count + 1
CREATE (entry: OntologyEntry {
  id: c.count,
  name: $name,
  abbreviation: $abbreviation,
  synonyms: $synonyms,
  description: $description
})-[:IN_VERSION]->(v)
WITH entry
CALL {
  WITH entry
  UNWIND $authors as author_id
  MATCH (person: Person {id: author_id})
  CREATE (person)-[authored:AUTHORED {time:datetime.transaction()}]->(entry)
  RETURN
    collect(person.id) as authors
}
CALL {
  WITH entry
  UNWIND $references as ref_id
  MATCH (reference: Reference {id: ref_id})
  CREATE (reference)-[ref_for:REFERENCE_FOR {time:datetime.transaction()}]->(entry)
  RETURN
    collect(reference.id) as references
}
CALL {
  WITH entry
  UNWIND $parents as parent_id
  MATCH (parent: OntologyEntry {id: parent_id})
  CREATE (parent)<-[:CHILD_OF {time:datetime.transaction()}]-(entry)
  RETURN
    collect(parent.id) as parents
}
RETURN entry {
  .*,
  labels: labels(entry),
  authors: authors,
  references: references,
  parents: parents,
  children: []
}