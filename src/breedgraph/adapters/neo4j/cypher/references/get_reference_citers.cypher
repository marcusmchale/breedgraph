// What cites each reference, for the release floor (docs/contributions.md §6).
// The ontology is shared, so a reference it cites (entries, including earlier versions, and commits) is public.
// Records are not controlled, so a reference a record cites is cited by its dataset.
MATCH (reference: Reference)
WHERE reference.id IN $reference_ids
RETURN
  reference.id AS reference_id,
  EXISTS { (reference)-[:REFERENCE_FOR]->(:OntologyEntry) }
    OR EXISTS { (reference)<-[:USES_LICENCE|USES_COPYRIGHT]-(:OntologyCommit|OntologyVersion) } AS public,
  [(reference)-[:REFERENCE_FOR]->(cited) WHERE NOT cited:OntologyEntry AND NOT cited:Record
    | {label: [label IN labels(cited) WHERE label IN $labels][0], id: cited.id}]
  + [(reference)-[:REFERENCE_FOR]->(:Record)<-[:INCLUDES_RECORD]-(dataset: Dataset) | {label: 'Dataset', id: dataset.id}]
  + [(reference)<-[:USES_LICENCE]-(study: Study) | {label: 'Study', id: study.id}] AS citers
