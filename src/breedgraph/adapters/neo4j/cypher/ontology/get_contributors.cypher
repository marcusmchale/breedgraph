// The people listed as contributors to the ontology at version $version, by their own agreement: Persons whose linked
// user agreed (ontology_credit), with work in that version. Their work is in it when they created or changed an entry
// or relationship still in that version (active, or deprecated in it and removed by the next), in a change it or an
// earlier version published (a change is stamped with the version it was made after, so it is published by a later
// one), or committed that version itself: a commit is credited with the version it made, and after that only through
// the work it published. Name, institution and ORCID iD only, as attribution needs, in name order.
MATCH (user: User)-[:IS_PERSON]->(person: Person {ontology_credit: true})
WHERE person.erased_at IS NULL AND (
  EXISTS {
    MATCH (user)-[:CONTRIBUTED]->(:UserOntologyContributions)-[:CONTRIBUTED]->(:OntologyEntryPatch)
      -[for_entry: FOR_ENTRY]->(:OntologyEntry)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle)
    WHERE for_entry.version < $version AND lifecycle.activated <= $version
      AND (lifecycle.deprecated IS NULL OR lifecycle.deprecated >= $version)
  }
  OR EXISTS {
    MATCH (user)-[:CONTRIBUTED]->(:UserOntologyContributions)-[:CONTRIBUTED]->(:OntologyRelationshipPatch)
      -[for_relationship: FOR_RELATIONSHIP]->(:OntologyRelationship)-[:HAS_LIFECYCLE]->(lifecycle: OntologyLifecycle)
    WHERE for_relationship.version < $version AND lifecycle.activated <= $version
      AND (lifecycle.deprecated IS NULL OR lifecycle.deprecated >= $version)
  }
  OR EXISTS {
    MATCH (user)-[:COMMITTED]->(:UserOntologyCommits)-[:COMMITTED]->(commit: OntologyCommit {version: $version})
  }
)
RETURN person.name AS name, person.institution AS institution, person.orcid AS orcid
ORDER BY toLower(person.name), person.id
