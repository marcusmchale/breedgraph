MATCH (relationship:OntologyRelationship)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle) where relationship.id in $relationship_ids
RETURN lifecycle {
        .*,
        relationship_id: relationship.id
       }
