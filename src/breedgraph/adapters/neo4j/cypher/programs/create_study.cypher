MATCH (trial: Trial {id: $trial_id})
MERGE (counter: count {name: 'study'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (trial)-[:HAS_STUDY]->(study: Study {
  id:          counter.count,
  name:        $name,
  fullname:    $fullname,
  description: $description,
  external_id: $external_id,
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
//Link factors (DataSet)
CALL {
  WITH study
  MATCH (factor: DataSet) WHERE factor.id in $factors
  CREATE (study)-[has_factor:HAS_FACTOR]->(factor)
  RETURN
    collect(factor.id) AS factors
}
//Link observations (DataSet)
CALL {
  WITH study
  MATCH (observation: DataSet) WHERE observation.id in $observations
  CREATE (study)-[has_observation:HAS_OBSERVATION]->(observation)
  RETURN
    collect(observation.id) AS observations
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
    factors: factors,
    observations: observations,
    design: design,
    licence: licence
  }