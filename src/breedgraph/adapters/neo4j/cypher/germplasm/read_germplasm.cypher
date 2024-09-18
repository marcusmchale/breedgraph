MATCH
  (captured: Germplasm {id: $entry})
OPTIONAL MATCH (captured)-[:SOURCE_FOR*]-(entry:Germplasm)
WITH captured, coalesce(collect(entry), []) AS germplasm
WITH captured + germplasm AS germplasm
UNWIND germplasm AS entry

RETURN entry {
       . *,
         methods:[(entry)-[:USES_METHOD]->(method:GermplasmMethod) | method.id],
         references: [(entry)<-[:REFERENCE_FOR]->(reference:Reference) | reference.id],
         sources: [(source:Germplasm)-[source_for:SOURCE_FOR]->(entry) | [source.id, entry.id, {type: source_for.type}]]
     }
