MATCH (patch:OntologyRelationshipPatch)-[for_relationship:FOR_RELATIONSHIP {version: $version}]->(relationship: OntologyRelationship)
WITH relationship.id as relationship_id, patch, for_relationship.time
ORDER BY relationship_id, for_relationship.time, elementId(patch)
RETURN relationship_id, collect(patch) as patches
