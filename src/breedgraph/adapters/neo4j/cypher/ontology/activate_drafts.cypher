MATCH (lifecycle: OntologyLifecycle)
WHERE
  lifecycle.drafted <= $version AND
  (lifecycle.activated IS NULL OR lifecycle.activated > $version) AND
  (lifecycle.deprecated IS NULL OR lifecycle.deprecated > $version)
SET
  lifecycle.activated = $version
