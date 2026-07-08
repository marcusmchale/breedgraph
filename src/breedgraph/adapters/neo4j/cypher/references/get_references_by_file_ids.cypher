MATCH (reference: Reference) where reference.file_id in $file_ids
RETURN
  reference {.*},
  [{label: "Reference", model_id: reference.id, key: "file_id"}] AS matches
