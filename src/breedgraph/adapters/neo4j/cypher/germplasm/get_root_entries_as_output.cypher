MATCH (entry: Germplasm)
WHERE NOT (entry)<-[:SOURCE_FOR]-(:Germplasm)
RETURN entry {
       .*,
         control_methods: [(entry)-[:USES_METHOD]->(method:ControlMethod) | method.id],
         references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ],
         sources: [],
         sinks: [(entry)-[rel:SOURCE_FOR]->(sink) | {source_id: entry.id, sink_id: sink.id, type: rel.source_type, description: rel.description}]
     }
