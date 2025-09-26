MATCH (entry: Germplasm) WHERE entry.id in $entry_ids
RETURN entry {
       .*,
         control_methods: [(entry)-[:USES_CONTROL_METHOD]->(method:GermplasmMethod) | method.id],
         references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ]
     }
