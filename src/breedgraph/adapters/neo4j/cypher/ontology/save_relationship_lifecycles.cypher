MATCH (user: User {id: $user_id})
MERGE (user)-[:MANAGED]->(mgmt:UserOntologyManagement)
WITH mgmt
UNWIND $lifecycles as lifecycle_data
MATCH (relationship:OntologyRelationship {id: lifecycle_data['relationship_id']})
MERGE (relationship)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle)
WITH lifecycle, lifecycle_data
SET lifecycle += lifecycle_data['versions']
// the entries it was deprecated with, if any (domain/services/ontology_lifecycles.py); null removes the property
SET lifecycle.deprecated_with = CASE WHEN size(lifecycle_data['deprecated_with']) > 0 THEN lifecycle_data['deprecated_with'] END
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
