MATCH (user: User {id: $user_id})
MERGE (user)-[:MANAGED]->(mgmt:UserOntologyManagement)
WITH mgmt
UNWIND $lifecycles as lifecycle_data
MATCH (source:OntologyEntry {id: lifecycle_data['source_id']})
        -[:HAS_RELATIONSHIP]->(rel:OntologyRelationship {label: lifecycle_data['label']})
        -[:RELATES_TO]->(target:OntologyEntry {id: lifecycle_data['target_id']})
MERGE (rel)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle)
SET rel += lifecycle_data['versions']
MERGE (mgmt)-[managed:MANAGED]->(lifecycle)
ON CREATE SET
  managed.phases = [lifecycle_data['current_phase']],
  managed.times = [datetime.transaction()]
ON MATCH SET
  managed.phases = managed.phases + lifecycle_data['current_phase'],
  managed.times = managed.times + datetime.transaction()
