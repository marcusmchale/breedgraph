MATCH (entry: Germplasm)
RETURN entry {
       .*,
         control_methods: [(entry)-[:USES_METHOD]->(method:ControlMethod) | method.id],
         references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ]
     }
