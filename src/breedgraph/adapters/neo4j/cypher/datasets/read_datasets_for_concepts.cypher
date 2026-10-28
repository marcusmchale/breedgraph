MATCH (dataset: Dataset)-[:FOR_CONCEPT]->(entry: Variable|Factor )
WHERE entry.id in $concept_ids
RETURN
  dataset {
    .*,
    study: [(dataset)-[:FOR_STUDY]->(study) | study.id][0],
    concept: [(dataset)-[:FOR_CONCEPT]-(concept:Variable|Factor) | concept.id][0],
    contributions: [(dataset)<-[contributed:CONTRIBUTED_TO]-(person:Person) | {person: person.id, roles: coalesce(contributed.roles, [])}],
    references: [(dataset)<-[:REFERENCE_FOR]-(reference:Reference)|reference.id],
    records: COLLECT {
      // newest first, as submitted, and those without a time last
      MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
      RETURN record {
        .*,
        .submitted,
        unit: unit.id,
        references: [(record)<-[:REFERENCE_FOR]-(ref:Reference)| ref.id],
        groups: [
          (record)-[:IN_GROUP]->(group:RecordGroup)<-[:HAS_GROUP]-(grouping:RecordGrouping) |
          {
            id: grouping.id,
            code: group.code
          }
        ]
      }
      ORDER BY record.submitted IS NULL, record.submitted DESC
    }
  }