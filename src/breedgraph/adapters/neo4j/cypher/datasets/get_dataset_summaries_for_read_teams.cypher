MATCH (study: Study {id: $study_id})
        <-[:FOR_STUDY]-(dataset: Dataset)
        -[:FOR_CONCEPT]->(concept: Variable | Factor),
      (dataset)<-[:CONTROLS]-(control: Control)
        <-[:CONTROLS]-(:TeamDatasets)
        <-[:CONTROLS]-(team: Team)

WITH concept, dataset, team, control
ORDER BY dataset.id, team.id, control.sequence DESC

WITH concept, dataset, team, collect(control)[0] as control
WITH concept, dataset, collect(team.id) as team_ids, collect(control.release) as releases

WITH concept, dataset, team_ids, min(releases) as effective_release
WHERE any(team_id in team_ids WHERE team_id in $read_teams)
OR effective_release >= $minimum_release

WITH concept, dataset

MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record),
      (record)-[:FOR_UNIT]->(unit:Unit)

OPTIONAL MATCH (block:Unit)-[:INCLUDES_UNIT*]->(unit) WHERE NOT (:Unit)-[:INCLUDES_UNIT]->(block)
WITH concept, dataset, record, unit, coalesce(block, unit) as block

OPTIONAL MATCH (unit)-[:OF_SUBJECT]->(subject:Subject)

CALL (unit, record) {
  OPTIONAL MATCH (unit)-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location:Location)
  WHERE (record.start IS NULL OR position.start IS NULL OR position.start < record.start)
  AND (record.end IS NULL OR position.end IS NULL OR position.end < record.end)
  RETURN collect(location.id) as location_ids
}

WITH
    concept.id as concept_id,
    dataset.id as id,
    collect(distinct subject.id) as subject_ids,
    location_ids,
    collect(distinct block.id) as block_ids,
    count(distinct unit) as unit_count,
    count(distinct record) as record_count,
    min(coalesce(record.start, record.end)) as start,
    max(coalesce(record.start, record.end)) as end

RETURN {
  id: id,
  concept_id: concept_id,
  subject_ids: subject_ids,
  location_ids: location_ids,
  block_ids: block_ids,
  unit_count: unit_count,
  record_count: record_count,
  start: start,
  end: end
 } as dataset_summary