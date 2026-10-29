MATCH (reference: Reference)
WHERE reference.seed_key IN $seed_keys
RETURN reference.seed_key AS seed_key, reference.id AS id
