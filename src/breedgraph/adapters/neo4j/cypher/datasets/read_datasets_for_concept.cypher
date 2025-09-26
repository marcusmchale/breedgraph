MATCH (dataset: DataSet)-[:FOR_CONCEPT]->(entry: Variable|Factor {id: $concept_id})
RETURN
  dataset {
    .*,
    concept: [(dataset)-[:FOR_CONCEPT]->(entry: Variable:Factor)|entry.id][0],
    contributors: [(dataset)<-[:CONTRIBUTED_TO]-(contributor:Person)|contributor.id],
    references: [(dataset)<-[:REFERENCE_FOR]-(reference:Reference)|reference.id],
    records: apoc.coll.sortMaps([
        (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit) |
        record {.*, .submitted, unit: unit.id, references: [(record)<-[:REFERENCE_FOR]-(ref:Reference)| ref.id]}
      ],'submitted')
  }