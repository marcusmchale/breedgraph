MERGE (c:Counter {name:'ontology'})
ON CREATE SET c.count = 0
WITH c
SET c.count = c.count + 1
CREATE (ontology: Ontology {
  id: c.count,
  name: $name,
  description: $description,
  version: $version,

  authors: $authors,
  references: $references,

  copyright: $copyright,
  licence: $licence
})

CALL {
  WITH ontology
  UNWIND $authors as author_id
  MATCH (person: Person {id: author_id})
  MERGE (person)-[authored:AUTHORED]->(ontology)
  ON CREATE SET authored.time = timestamp()
  RETURN
    collect(person.id) as authors
}
CALL {
  WITH ontology
  UNWIND $references as ref_id
  MATCH (reference: Reference {id: ref_id})
  MERGE (reference)-[ref_for:REFERENCE_FOR]->(ontology)
  ON CREATE SET authored.time = timestamp()
  RETURN
    collect(person.id) as authors
}
CALL {
  WITH ontology
  MATCH (reference: Reference {id: $copyright})
  MERGE (reference)-[ref_for:REFERENCE_FOR]->(ontology)
  ON CREATE SET authored.time = timestamp()
  RETURN
    collect(person.id) as authors
}


RETURN ontology {
  .id, .name, .description,.version,.authors,.references,.copyright, .licence,
  parent: NULL,
  children: NULL,
  references: []
  uses: []
}