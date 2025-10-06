MATCH (user: User {id: $user_id})
MERGE (user)-[:MANAGED]->(mgmt:UserOntologyManagement)
WITH mgmt
UNWIND $lifecycles as lifecycle_data
MATCH (relationship:OntologyRelationship {id: lifecycle_data['relationship_id']})
MERGE (relationship)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle)
WITH lifecycle, lifecycle_data
SET lifecycle += lifecycle_data['versions']
MERGE (mgmt)-[managed:MANAGED]->(lifecycle)
ON CREATE SET
  managed.phases = [lifecycle_data['current_phase']],
  managed.times = [datetime.transaction()]
ON MATCH SET
  managed.phases = managed.phases + lifecycle_data['current_phase'],
  managed.times = managed.times + datetime.transaction()
