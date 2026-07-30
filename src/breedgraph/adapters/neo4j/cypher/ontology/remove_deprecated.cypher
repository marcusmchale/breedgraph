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
  managed.phases = ["DEPRECATED"],
  managed.times = [datetime.transaction()]
ON MATCH SET
  managed.phases = managed.phases + "DEPRECATED",
  managed.times = managed.times + datetime.transaction()

