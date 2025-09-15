MATCH (program: Program {name_lower: $name_lower})
RETURN
  program {
    .*,
    contacts: [(program)-[:HAS_CONTACT]->(contact:Person)|contact.id],
    references: [(reference:Reference)-[:REFERENCE_FOR]->(program)|reference.id],
    trials: [
      (program)-[:HAS_TRIAL]->(trial:Trial) | trial {
        .*,
        contacts: [(trial)-[:HAS_CONTACT]->(contact:Person)|contact.id],
        references: [(reference:Reference)-[:REFERENCE_FOR]->(trial)|reference.id],
        studies: [(trial)-[:HAS_STUDY]->(study:Study) | study {
          .*,
          references: [(reference:Reference)-[:REFERENCE_FOR]->(study)|reference.id],
          datasets: [(study)-[:HAS_DATASET]->(dataset:DataSet)|dataset.id],
          design: [(study)-[:USES_DESIGN]->(design:Design)|design.id][0],
          licence: [(study)-[:USES_LICENCE]->(licence:Reference)|licence.id][0]
          }
        ]
      }
    ]
  }