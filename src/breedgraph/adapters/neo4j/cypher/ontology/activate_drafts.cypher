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
ON MATCH SET
  managed.phases = managed.phases + "ACTIVE",
  managed.times = managed.times + datetime.transaction()
