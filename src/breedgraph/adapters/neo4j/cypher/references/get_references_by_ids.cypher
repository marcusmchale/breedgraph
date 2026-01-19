MATCH (reference: Reference) where reference.id in $reference_ids
RETURN
  reference {.*}
