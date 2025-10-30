MATCH (entry: Germplasm) WHERE entry.name_lower in $names_lower
RETURN entry {
       .*,
         control_methods: [(entry)-[:USES_CONTROL_METHOD]->(method:ControlMethod) | method.id],
         references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ],
         sources: [(source)-[rel:SOURCE_FOR]->(entry) | {source_id: source.id, sink_id: entry.id, type: rel.source_type, description: rel.description}],
         sinks: [(entry)-[rel:SOURCE_FOR]->(sink) | {source_id: entry.id, sink_id: sink.id, type: rel.source_type, description: rel.description}]
     }
