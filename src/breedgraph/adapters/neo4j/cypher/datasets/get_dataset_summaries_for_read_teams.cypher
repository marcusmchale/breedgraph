MATCH (study: Study {id: $study_id})
        -[:HAS_DATASET]->(dataset:Dataset)
        -[:FOR_CONCEPT]->(concept:Variable|Factor),
      (dataset)<-[controls:CONTROLS]-(:TeamDatasets)<-[:CONTROLS]-(team:Team)
WITH concept, dataset, team, last(controls.releases) as release
WITH concept, dataset where team.id in $read_teams OR release = "PUBLIC"
WITH DISTINCT concept, dataset

MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record),
      (record)-[:FOR_UNIT]->(unit:Unit),
      (unit)-[:OF_SUBJECT]->(subject:Subject)

OPTIONAL MATCH (unit)-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location:Location)
    WHERE (record.start IS NULL OR position.start IS NULL OR position.start < record.start)
    AND (record.end IS NULL OR position.end IS NULL OR position.end < record.end)

OPTIONAL MATCH (block)-[:INCLUDES_UNIT*]->(unit)

WITH
    dataset.id as id,
    concept.id as concept_id,
    collect(distinct subject.id) as subject_ids,
    collect(distinct location.id) as location_ids,
    collect(distinct coalesce(block.id, unit.id)) as block_ids,
    count(unit) as unit_count,
    count(record) as record_count,
    min(record.start) as start,
    max(record.end) as end

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