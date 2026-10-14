// Dataset headers by id, study and/or concept (null parameters match everything), each with a readable flag resolved
// from its current control teams and the given read teams and minimum release, and its record count.
// Records are read separately (read_dataset_records); contributors and references only for readable datasets,
// as DatasetStored.redacted gives registered users.
MATCH (dataset:Dataset)
WHERE ($dataset_ids IS NULL OR dataset.id IN $dataset_ids)
  AND ($study_ids IS NULL OR EXISTS { (dataset)-[:FOR_STUDY]->(study:Study) WHERE study.id IN $study_ids })
  AND ($concept_ids IS NULL OR EXISTS { (dataset)-[:FOR_CONCEPT]->(concept:Variable|Factor) WHERE concept.id IN $concept_ids })

CALL (dataset) {
  OPTIONAL MATCH (dataset)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:TeamDatasets)<-[:CONTROLS]-(team:Team)
  WITH team, control
  ORDER BY team.id, control.sequence DESC
  WITH team, collect(control)[0] AS control
  WHERE team IS NULL OR NOT coalesce(control.ended, false)
  RETURN collect(team.id) AS team_ids, collect(control.release) AS releases
}

WITH dataset,
  CASE
    WHEN size(team_ids) = 0 THEN true
    WHEN any(team_id IN team_ids WHERE team_id IN $read_teams) THEN true
    ELSE reduce(lowest = 2, release IN releases | CASE WHEN release < lowest THEN release ELSE lowest END) >= $minimum_release
  END AS readable

RETURN dataset {
  id: dataset.id,
  study: [(dataset)-[:FOR_STUDY]->(study:Study) | study.id][0],
  concept: [(dataset)-[:FOR_CONCEPT]->(concept:Variable|Factor) | concept.id][0],
  contributors: CASE WHEN readable THEN [(dataset)<-[:CONTRIBUTED_TO]-(contributor:Person) | contributor.id] ELSE [] END,
  references: CASE WHEN readable THEN [(dataset)<-[:REFERENCE_FOR]-(reference:Reference) | reference.id] ELSE [] END,
  record_count: COUNT { (dataset)-[:INCLUDES_RECORD]->(:Record) },
  readable: readable
} AS dataset
ORDER BY dataset.id
