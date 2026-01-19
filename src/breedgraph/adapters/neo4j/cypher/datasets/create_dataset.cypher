MERGE (counter: Counter {name: 'dataset'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (dataset: Dataset {id: counter.count})
WITH
  dataset
//Link study
CALL (dataset) {
  MATCH (study: Study {id: $study})
  CREATE (study)-[:HAS_DATASET]->(dataset)
  RETURN
    collect(study.id)[0] as study
}
//Link concept
CALL (dataset) {
  MATCH (concept: Variable|Factor {id: $concept})
  CREATE (dataset)-[for_concept:FOR_CONCEPT]->(concept)
  RETURN
    collect(concept.id)[0] AS concept
}
//Link contributors
CALL (dataset) {
  MATCH (contributor: Person) WHERE contributor.id IN $contributors
  CREATE (contributor)-[contributed:CONTRIBUTED_TO]->(dataset)
  RETURN
    collect(contributor.id) AS contributors
}
//Link references
CALL (dataset){
  MATCH (reference: Reference) WHERE reference.id IN $references
  CREATE (reference)-[reference_for: REFERENCE_FOR]->(dataset)
  RETURN
    collect(reference.id) AS references
}

RETURN
  dataset {
    .*,
    study: study,
    concept: concept,
    records: [],
    contributors: contributors,
    references: references
  }