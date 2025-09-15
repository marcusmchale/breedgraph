MATCH (entry: OntologyEntry) WHERE entry.id in $entry_ids
RETURN entry {
    .*,
    label: [label IN labels(entry) WHERE label <> "OntologyEntry"][0],
    authors: [(author: Person)-[authored:AUTHORED]-(entry) | author.id ],
    references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ],
    relationships: [
      (source)-[:HAS_RELATIONSHIP]->(ontology_relationship:OntologyRelationship)-[:RELATES_TO]->(target: OntologyEntry)
       WHERE source = entry OR target = entry |
       {
        source_id: source.id,
        source_label: [label IN labels(source) WHERE label <> "OntologyEntry"][0],
        target_id: target.id,
        target_label: [label IN labels(target) WHERE label <> "OntologyEntry"][0],
        relationship_type: [label IN labels(ontology_relationship) WHERE label <> "OntologyRelationship"][0],
        properties: properties(ontology_relationship)
      }
    ]
  } as entry
