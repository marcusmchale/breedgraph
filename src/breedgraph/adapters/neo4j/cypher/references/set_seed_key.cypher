MATCH (reference: Reference {id: $reference_id})
SET reference.seed_key = $seed_key
