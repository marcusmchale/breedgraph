MATCH (reference: Reference) where reference.id in $reference_ids
RETURN
  reference {.*, contributions: [(reference)<-[contributed:CONTRIBUTED_TO]-(person:Person) | {person: person.id, roles: coalesce(contributed.roles, [])}]}
