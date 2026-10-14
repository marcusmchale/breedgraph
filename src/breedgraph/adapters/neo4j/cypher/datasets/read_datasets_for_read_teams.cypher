// Datasets by id, study and/or concept (null parameters match everything), each with a readable flag resolved
// from its current control teams and the given read teams and minimum release.
// Records, contributors and references are only returned for readable datasets, as DatasetStored.redacted does.
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
  .*,
  study: [(dataset)-[:FOR_STUDY]->(study:Study) | study.id][0],
  concept: [(dataset)-[:FOR_CONCEPT]->(concept:Variable|Factor) | concept.id][0],
  contributors: CASE WHEN readable THEN [(dataset)<-[:CONTRIBUTED_TO]-(contributor:Person) | contributor.id] ELSE [] END,
  references: CASE WHEN readable THEN [(dataset)<-[:REFERENCE_FOR]-(reference:Reference) | reference.id] ELSE [] END,
  records: CASE WHEN readable THEN apoc.coll.sortMaps([
    (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit) |
    record {
      .*,
      unit: unit.id,
      references: [(record)<-[:REFERENCE_FOR]-(reference:Reference) | reference.id],
      groups: [
        (record)-[:IN_GROUP]->(group:RecordGroup)<-[:HAS_GROUP]-(grouping:RecordGrouping) |
        { id: grouping.id, code: group.code }
      ]
    }
  ], 'submitted') ELSE [] END,
  readable: readable
} AS dataset
ORDER BY dataset.id
