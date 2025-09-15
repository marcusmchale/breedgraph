MATCH (trial: Trial {id: $trial_id})
MERGE (counter: Counter {name: 'study'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (trial)-[:HAS_STUDY]->(study: Study {
  id:          counter.count,
  name:        $name,
  fullname:    $fullname,
  description: $description,
  practices:   $practices,
  start: datetime($start['str']),
  start_unit: datetime($start['unit']),
  start_step: datetime($start['step']),
  end: datetime($end['str']),
  end_unit: datetime($end['unit']),
  end_step: datetime($end['step'])
})

WITH
  study
//Link references
CALL {
  WITH study
  MATCH (reference: Reference) WHERE reference.id IN $references
  CREATE (reference)-[:REFERENCE_FOR ]->(study)
  RETURN
    collect(reference.id) AS references
}
//Link datasets
CALL {
  WITH study
  MATCH (dataset: DataSet) WHERE dataset.id in $datasets
  CREATE (study)-[has_dataset:HAS_DATASET]->(dataset)
  RETURN
    collect(dataset.id) AS datasets
}
//Link design (in ontology)
CALL {
  WITH study
  MATCH (design: Design) WHERE design.id = $design
  CREATE (study)-[uses_design:USES_DESIGN]->(design)
  RETURN
    collect(design.id)[0] AS design
}
//Link licence (reference)
CALL {
  WITH study
  MATCH (licence: Reference) WHERE licence.id = $licence
  CREATE (study)-[uses_licence:USES_LICENCE]->(licence)
  RETURN
    collect(licence.id)[0] AS licence
}
RETURN
  study {
    .*,
    references: references,
    datasets: datasets,
    design: design,
    licence: licence
  }