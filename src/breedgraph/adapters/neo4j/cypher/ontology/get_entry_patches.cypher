MATCH (patch:OntologyEntryPatch)-[for_entry:FOR_ENTRY {version: $version}]->(entry: OntologyEntry)
WITH entry.id as entry_id, patch, for_entry.time
ORDER BY entry_id, for_entry.time, elementId(patch)
RETURN entry_id, collect(patch) as patches
