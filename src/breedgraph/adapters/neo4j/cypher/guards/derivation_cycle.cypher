MATCH (unit: Unit {id: $unit_id})
RETURN EXISTS {
  MATCH (source: Unit)-[:DERIVED_FROM]->+(unit)
  WHERE source.id IN $source_ids
} as in_use
