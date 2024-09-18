MATCH (root: Germplasm) WHERE NOT (root)<-[:SOURCE_FOR]-(:Germplasm)
OPTIONAL MATCH (root)-[:SOURCE_FOR*]->(child:Germplasm)
WITH root, coalesce(collect(child), []) AS children
WITH root + children AS germplasm
RETURN [entry IN germplasm |
  entry {
  . *,
    methods:[(entry)-[:USES_METHOD]->(method:GermplasmMethod) | method.id],
    references:[(entry)<-[:REFERENCE_FOR]->(reference:Reference) | reference.id],
    sources: [(source:Germplasm)- [source_for:SOURCE_FOR] - >(entry) | [source.id, entry.id, {type:source_for.type}]]
  }
] AS germplasm