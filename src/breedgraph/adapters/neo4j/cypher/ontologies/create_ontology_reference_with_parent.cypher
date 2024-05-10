MATCH (parent: Ontology {id: $parent})
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
})-[:WITHIN_ONTOLOGY]->(parent)
RETURN ontology {
  .*,
  parent: parent.id,
  children: NULL,
  uses: []
}