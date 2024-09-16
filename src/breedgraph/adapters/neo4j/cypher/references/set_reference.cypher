MATCH
  (reference: Reference {id: $reference_id})
SET
  reference += $params
RETURN
  reference {.*}