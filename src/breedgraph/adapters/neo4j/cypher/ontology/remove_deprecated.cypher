MATCH (lifecycle: OntologyLifecycle)
WHERE
  lifecycle.deprecated <= $version AND
  (lifecycle.removed IS NULL OR lifecycle.removed > $version)
SET
  lifecycle.removed = $version
