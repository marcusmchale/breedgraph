MATCH (dataset: Dataset)-[:FOR_STUDY]->(study:Study)
WHERE study.id in $study_ids
RETURN
  dataset {
    .*,
    study: [(dataset)-[:FOR_STUDY]->(study) | study.id][0],
    concept: [(dataset)-[:FOR_CONCEPT]-(concept:Variable|Factor) | concept.id][0],
    contributors: [(dataset)<-[:CONTRIBUTED_TO]-(contributor:Person)|contributor.id],
    references: [(dataset)<-[:REFERENCE_FOR]-(reference:Reference)|reference.id],
    records: apoc.coll.sortMaps([
      (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit) |
      record {
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
    ],'submitted')
  }