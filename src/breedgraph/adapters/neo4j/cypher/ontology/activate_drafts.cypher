MATCH (user: User {id: $user_id})
MERGE (user)-[:MANAGED]->(mgmt:UserOntologyManagement)
WITH mgmt
MATCH (lifecycle: OntologyLifecycle)
WHERE
  lifecycle.drafted <= $version AND
  (lifecycle.activated IS NULL OR lifecycle.activated > $version) AND
  (lifecycle.deprecated IS NULL OR lifecycle.deprecated > $version)
SET
  lifecycle.activated = $version
MERGE (mgmt)-[managed:MANAGED]->(lifecycle)
ON CREATE SET
  managed.phases = ["ACTIVE"],
  managed.times = [datetime.transaction()]
// a second change in the same transaction replaces the phase recorded for it
ON MATCH SET
  managed.phases = CASE WHEN last(managed.times) = datetime.transaction()
    THEN managed.phases[..-1] + "ACTIVE"
    ELSE managed.phases + "ACTIVE" END,
  managed.times = CASE WHEN last(managed.times) = datetime.transaction()
    THEN managed.times
    ELSE managed.times + datetime.transaction() END
