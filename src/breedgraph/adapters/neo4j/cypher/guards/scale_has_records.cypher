// Records of a scale: of a variable or factor that reads it as data cites it (scale_categories_cited.cypher), through
// a relationship not removed, or removed with the variable or factor
MATCH (scale: Scale {id: $scale_id})
RETURN EXISTS {
  MATCH (concept: Variable|Factor)-[:HAS_RELATIONSHIP]->(uses: UsesScale)-[:RELATES_TO]->(scale),
    (uses)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle),
    (concept)<-[:FOR_CONCEPT]-(:Dataset)-[:INCLUDES_RECORD]->(:Record)
  WHERE lifecycle.removed IS NULL OR concept.id IN coalesce(lifecycle.deprecated_with, [])
} as in_use
