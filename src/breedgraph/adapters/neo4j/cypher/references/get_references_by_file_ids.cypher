MATCH (reference: Reference) where reference.file_id in $file_ids
RETURN
  reference {.*}
