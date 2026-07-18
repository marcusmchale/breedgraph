MATCH (relationship:OntologyRelationship {id: $relationship_id})
OPTIONAL MATCH (patch: OntologyRelationshipPatch)-[for_rel:FOR_RELATIONSHIP]->(relationship)
WHERE for_rel.version <= $version
WITH relationship, patch, for_rel
ORDER BY for_rel.time
WITH relationship, collect(patch {.*}) as patches
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
    } as relationship,
    patches