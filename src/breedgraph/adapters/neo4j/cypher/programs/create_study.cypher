MATCH (trial: Trial {id: $trial_id})
MERGE (counter: Counter {name: 'study'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (trial)-[:HAS_STUDY]->(study: Study {id: counter.count})
SET study += $study_data

WITH
  study
//Link references
OPTIONAL CALL (study) {
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  CREATE (reference)-[:REFERENCE_FOR ]->(study)
  RETURN
    collect(reference.id) AS references
}
//Link design (in ontology)
OPTIONAL CALL (study) {
  MATCH (design: Design) WHERE design.id = $design_id
  CREATE (study)-[uses_design:USES_DESIGN]->(design)
  RETURN
    collect(design.id)[0] AS design
}
//Link licence (reference)
OPTIONAL CALL (study) {
  MATCH (licence: Reference) WHERE licence.id = $licence_id
  CREATE (study)-[uses_licence:USES_LICENCE]->(licence)
  RETURN
    collect(licence.id)[0] AS licence
}
// Create groupings and scopes
OPTIONAL CALL (study) {
  UNWIND $groupings AS grouping_data
    CREATE (study)-[:USES_GROUPING]->(grouping:RecordGrouping { name: grouping_data.name })
    WITH grouping, grouping_data
    OPTIONAL CALL (grouping, grouping_data) {
      UNWIND grouping_data.scopes AS scope_data
        CREATE (grouping)-[:HAS_SCOPE]->(scope: GroupingScope)
        WITH scope, scope_data
        MATCH (dataset: Dataset) WHERE dataset.id IN scope_data.dataset_ids
        CREATE (scope)<-[:IN_SCOPE]-(dataset)
        WITH scope, collect(dataset.id) as dataset_ids
      RETURN collect({ dataset_ids: dataset_ids }) as scopes
    }
  RETURN collect({name: grouping.name, scopes: scopes}) as groupings
}

RETURN
  study {
    .*,
    reference_ids: references,
    design_id: design,
    licence_id: licence,
    groupings: groupings
  }