UNWIND $patches AS item
MATCH (entry:OntologyEntry {id: item.entry_id})
SET entry += item.patch

