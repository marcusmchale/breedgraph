MATCH (trial: Trial {id: $trial_id})
MERGE (counter: Counter {name: 'study'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (trial)-[:HAS_STUDY]->(study: Study {id: counter.count})
SET study += $study_data

WITH
  study
//Link references
CALL {
  WITH study
  MATCH (reference: Reference) WHERE reference.id IN $reference_ids
  CREATE (reference)-[:REFERENCE_FOR ]->(study)
  RETURN
    collect(reference.id) AS references
}
//Link datasets
CALL {
  WITH study
  MATCH (dataset: Dataset) WHERE dataset.id in $dataset_ids
  CREATE (study)-[has_dataset:HAS_DATASET]->(dataset)
  RETURN
    collect(dataset.id) AS datasets
}
//Link design (in ontology)
CALL {
  WITH study
  MATCH (design: Design) WHERE design.id = $design_id
  CREATE (study)-[uses_design:USES_DESIGN]->(design)
  RETURN
    collect(design.id)[0] AS design
}
//Link licence (reference)
CALL {
  WITH study
  MATCH (licence: Reference) WHERE licence.id = $licence_id
  CREATE (study)-[uses_licence:USES_LICENCE]->(licence)
  RETURN
    collect(licence.id)[0] AS licence
}
RETURN
  study {
    .*,
    reference_ids: references,
    dataset_ids: datasets,
    design_id: design,
    licence_id: licence
  }