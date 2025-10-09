MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle) where entry.id in $entry_ids
RETURN lifecycle {
        .*,
        entry_id: entry.id
       }
