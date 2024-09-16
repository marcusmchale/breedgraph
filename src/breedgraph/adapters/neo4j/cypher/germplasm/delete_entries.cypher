MATCH (entry: GermplasmEntry) where entry.id in $entry_ids
DETACH DELETE (entry)