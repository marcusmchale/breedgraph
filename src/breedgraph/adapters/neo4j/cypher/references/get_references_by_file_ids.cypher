MATCH (reference: Reference) where reference.file_id in $file_ids
RETURN
  reference {.*, contributions: [(reference)<-[contributed:CONTRIBUTED_TO]-(person:Person) | {person: person.id, roles: coalesce(contributed.roles, [])}]},
  [{label: "Reference", model_id: reference.id, key: "file_id"}] AS matches
