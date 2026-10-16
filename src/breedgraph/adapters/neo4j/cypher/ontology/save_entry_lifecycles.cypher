MATCH (user: User {id: $user_id})
MERGE (user)-[:MANAGED]->(mgmt:UserOntologyManagement)
WITH mgmt
UNWIND $lifecycles as lifecycle_data
MATCH (entry:OntologyEntry {id: lifecycle_data['entry_id']})
MERGE (entry)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle)
SET lifecycle += lifecycle_data['versions']
MERGE (mgmt)-[managed:MANAGED]->(lifecycle)
ON CREATE SET
  managed.phases = [lifecycle_data['current_phase']],
  managed.times = [datetime.transaction()]
// a second change in the same transaction replaces the phase recorded for it
ON MATCH SET
  managed.phases = CASE WHEN last(managed.times) = datetime.transaction()
    THEN managed.phases[..-1] + lifecycle_data['current_phase']
    ELSE managed.phases + lifecycle_data['current_phase'] END,
  managed.times = CASE WHEN last(managed.times) = datetime.transaction()
    THEN managed.times
    ELSE managed.times + datetime.transaction() END
