MERGE (counter: Counter {name: 'dataset'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (dataset: Dataset {id: counter.count})
WITH
  dataset
//Link study
CALL (dataset) {
  MATCH (study: Study {id: $study})
  CREATE (dataset)-[:FOR_STUDY]->(study)
  RETURN study.id AS study
}
//Link concept
CALL (dataset) {
  MATCH (concept: Variable|Factor {id: $concept})
  CREATE (dataset)-[for_concept:FOR_CONCEPT]->(concept)
  RETURN concept.id AS concept
}
//Link contributions: the Persons credited, with the roles they had
OPTIONAL CALL (dataset) {
  UNWIND $contributions AS contribution
  MATCH (person: Person {id: contribution.person})
  CREATE (person)-[contributed:CONTRIBUTED_TO {roles: contribution.roles}]->(dataset)
  RETURN
    collect({person: person.id, roles: contributed.roles}) AS contributions
}
//Link references
OPTIONAL CALL (dataset){
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
    contributions: contributions,
    references: references
  }