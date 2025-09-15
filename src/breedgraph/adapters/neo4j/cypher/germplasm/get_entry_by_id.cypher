MATCH (entry: Germplasm {id: $entry_id})
RETURN entry {
       .*,
         methods: [(entry)-[:USES_METHOD]->(method:GermplasmMethod) | method.id],
         references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ]
     }
