MATCH (entry: Germplasm) WHERE entry.name_lower in $names_lower
RETURN entry {
       .*,
         control_methods: [(entry)-[:USES_CONTROL_METHOD]->(method:ControlMethod) | method.id],
         references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ]
     }
