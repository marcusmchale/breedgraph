MATCH (reference: Reference)
RETURN
  reference {.*, contributions: [(reference)<-[contributed:CONTRIBUTED_TO]-(person:Person) | {person: person.id, roles: coalesce(contributed.roles, [])}]}
