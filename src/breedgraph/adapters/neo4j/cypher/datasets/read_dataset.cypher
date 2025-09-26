MATCH (dataset: DataSet {id: $dataset_id})
RETURN
  dataset {
    .*,
    concept: [(dataset)-[:FOR_CONCEPT]-(concept:Variable|Factor) | concept.id][0],
    contributors: [(dataset)<-[:CONTRIBUTED_TO]-(contributor:Person)|contributor.id],
    references: [(dataset)<-[:REFERENCE_FOR]-(reference:Reference)|reference.id],
    records: apoc.coll.sortMaps([
      (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit) |
      record {.*, .submitted, unit: unit.id, references: [(record)<-[:REFERENCE_FOR]-(ref:Reference)| ref.id]}
    ],'submitted')
  }