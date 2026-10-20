// When the retention job first found a file reference that nothing cites (as guards/reference_in_use.cypher):
// set the first time it is found unused, and cleared once something cites it again. Only changes are written.
MATCH (reference: Reference)
WHERE reference.type IN ['FILE', 'DATA_FILE']
WITH reference,
  EXISTS { (reference)-[:REFERENCE_FOR]->() } OR EXISTS { (reference)<-[:USES_LICENCE|USES_COPYRIGHT]-() } AS in_use
WHERE in_use = (reference.unused_since IS NOT NULL)
SET reference.unused_since = CASE WHEN in_use THEN null ELSE datetime.transaction() END
