MERGE (c:Counter {name:'ontology_entry'})
ON CREATE SET c.count = 0
SET c.count = c.count + 1
MATCH (v:OntologyVersion {major:$major, minor:$minor, patch:$patch})
CREATE (entry: Term:OntologyEntry {
  id: c.count,
  name: $name,
  abbreviation: $abbreviation,
  synonyms: $synonyms,
  description: $description
})-[:IN_VERSION]->(v)

CALL {
  WITH entry
  UNWIND $authors as author_id
  MATCH (person: Person {id: author_id})
  CREATE (person)-[authored:AUTHORED]->(entry)
  RETURN
    collect(person.id) as authors
}
CALL {
  WITH entry
  UNWIND $references as ref_id
  MATCH (reference: Reference {id: ref_id})
  CREATE (reference)-[ref_for:REFERENCE_FOR]->(entry)
  RETURN
    collect(reference.id) as references
}
/// Merge in parent child relationships
/// as other entries store the same information
CALL {
  WITH entry
  UNWIND $parents as parent_id
  MATCH (parent: OntologyEntry {id: parent_id})
  MERGE (parent)<-[:CHILD_OF]-(entry)
  RETURN
    collect(parent.id) as parents
}
CALL {
  WITH entry
  UNWIND $children as child_id
  MATCH (child: OntologyEntry {id: child_id})
  MERGE (child)-[:CHILD_OF]->(entry)
  RETURN
    collect(child.id) as children
}

RETURN entry {
  .*,
  parents: parents,
  children: children,
  references: []
}