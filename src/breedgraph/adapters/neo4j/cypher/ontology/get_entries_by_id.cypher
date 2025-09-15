MATCH (entry: OntologyEntry) WHERE entry.id in $entry_ids
RETURN entry {
    .*,
    label: [label IN labels(entry) WHERE label <> "OntologyEntry"][0],
    authors: [(author: Person)-[authored:AUTHORED]-(entry) | author.id ],
    references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ]
  } as entry
