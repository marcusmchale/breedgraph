MATCH (relationship:OntologyRelationship {id: $relationship_id})
MATCH (source: OntologyEntry)
        -[:HAS_RELATIONSHIP]->(relationship)
        -[:RELATES_TO]->(target: OntologyEntry)
RETURN
    relationship {
        .*,
        label: [label IN labels(relationship) WHERE label <> "OntologyRelationship"][0],
        source_id: source.id,
        target_id: target.id,
        source_label: [label IN labels(source) WHERE label <> "OntologyEntry"][0],
        target_label: [label IN labels(target) WHERE label <> "OntologyEntry"][0]
    } as relationship