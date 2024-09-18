MATCH (dataset: DataSet {id: $dataset_id})
RETURN
  dataset {
    .*,
    term: [(dataset)-[:FOR_TERM]-(term: Variable|EventType|Parameter)|term.id][0],
    contributors: [(dataset)<-[:CONTRIBUTED_TO]-(contributor:Person)|contributor.id],
    references: [(dataset)<-[:REFERENCE_FOR]-(reference:Reference)|reference.id],
    unit_records: [
      (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit) |
        [
          unit.id,
          apoc.coll.sortMaps([
            record {.*, .submitted, references: [(record)<-[:REFERENCE_FOR]-(ref:Reference)| ref.id]}
          ],'submitted')
        ]
    ]
  }