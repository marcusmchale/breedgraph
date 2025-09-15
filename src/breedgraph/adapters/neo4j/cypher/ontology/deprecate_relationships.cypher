MATCH (user: User {id: $user_id})
UNWIND $relationships as rels
WITH user, rels[0] as source_id, rels[1] as sink_id
MATCH (source: OntologyEntry {id: source_id})-[relationship]->(sink: OntologyEntry {id: sink_id})
WHERE type(relationship) = $label
SET relationship.deprecated = $version
CREATE (user)-[:DEPRECATED_RELATIONSHIP {relationship: $label, sink: $sink_id, time:datetime.date.transaction()}]->(entry)