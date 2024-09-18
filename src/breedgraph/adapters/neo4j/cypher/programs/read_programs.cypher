MATCH (program: Program)
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
          factors: [(study)-[:HAS_FACTOR]->(factor:DataSet)|factor.id],
          observations: [(study)-[:HAS_OBSERVATION]->(observation:DataSet)|observation.id],
          design: [(study)-[:USES_DESIGN]->(design:Design)|design.id][0],
          licence: [(study)-[:USES_LICENCE]->(licence:Reference)|licence.id][0]
          }
        ]
      }
    ]
  }
