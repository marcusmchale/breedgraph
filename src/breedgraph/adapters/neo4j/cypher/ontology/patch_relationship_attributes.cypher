MATCH (relationship: OntologyRelationship {id: $relationship_id})
CREATE (patch: OntologyRelationshipPatch)
         -[:FOR_RELATIONSHIP {version: $version, time: datetime.transaction()}]->(relationship)
SET patch += $attributes
WITH patch
// Link contributor
CALL (patch) {
  MATCH (user: User { id: $user_id })
  MERGE (user)-[c:CONTRIBUTED]->(contributions: UserOntologyContributions)
  CREATE (contributions)-[contributed:CONTRIBUTED {time:datetime.transaction()}]->(patch)
}