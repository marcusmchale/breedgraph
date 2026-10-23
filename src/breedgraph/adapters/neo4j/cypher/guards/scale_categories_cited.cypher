// The names records cite of a scale's categories: the values of the records of each variable or factor that reads
// the scale as data cites it (ontology_entries_referential.cypher), through a relationship not removed, or removed
// with the variable or factor
MATCH (concept: Variable|Factor)-[:HAS_RELATIONSHIP]->(uses: UsesScale)-[:RELATES_TO]->(:Scale {id: $scale_id}),
  (uses)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle)
WHERE lifecycle.removed IS NULL OR concept.id IN coalesce(lifecycle.deprecated_with, [])
OPTIONAL MATCH (concept)<-[:FOR_CONCEPT]-(:Dataset)-[:INCLUDES_RECORD]->(record: Record)
WHERE record.value IS NOT NULL
RETURN collect(DISTINCT record.value) AS names
