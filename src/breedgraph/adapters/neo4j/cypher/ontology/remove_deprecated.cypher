MATCH (user: User {id: $user_id})
MERGE (user)-[:MANAGED]->(mgmt:UserOntologyManagement)
WITH mgmt
MATCH (lifecycle: OntologyLifecycle)
WHERE
  lifecycle.deprecated <= $version AND
  (lifecycle.removed IS NULL OR lifecycle.removed > $version)
SET
  lifecycle.removed = $version
MERGE (mgmt)-[managed:MANAGED]->(lifecycle)
ON CREATE SET
  managed.phases = ["REMOVED"],
  managed.times = [datetime.transaction()]
// a second change in the same transaction replaces the phase recorded for it
ON MATCH SET
  managed.phases = CASE WHEN last(managed.times) = datetime.transaction()
    THEN managed.phases[..-1] + "REMOVED"
    ELSE managed.phases + "REMOVED" END,
  managed.times = CASE WHEN last(managed.times) = datetime.transaction()
    THEN managed.times
    ELSE managed.times + datetime.transaction() END
