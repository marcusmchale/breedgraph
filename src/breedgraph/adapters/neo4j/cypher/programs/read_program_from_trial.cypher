MATCH (: Trial {id: $trial_id})<-[:HAS_TRIAL]-(program:Program)
RETURN
  program {
    .*,
    contact_ids: [(program)-[:HAS_CONTACT]->(contact:Person)|contact.id],
    reference_ids: [(reference:Reference)-[:REFERENCE_FOR]->(program)|reference.id],
    trials: [
      (program)-[:HAS_TRIAL]->(trial:Trial) | trial {
        .*,
        contact_ids: [(trial)-[:HAS_CONTACT]->(contact:Person)|contact.id],
        reference_ids: [(reference:Reference)-[:REFERENCE_FOR]->(trial)|reference.id],
        studies: [(trial)-[:HAS_STUDY]->(study:Study) | study {
          .*,
          reference_ids: [(reference:Reference)-[:REFERENCE_FOR]->(study)|reference.id],
          dataset_ids: [(study)-[:HAS_DATASET]->(dataset:DataSet)|dataset.id],
          design_id: [(study)-[:USES_DESIGN]->(design:Design)|design.id][0],
          licence_id: [(study)-[:USES_LICENCE]->(licence:Reference)|licence.id][0]
          }
        ]
      }
    ]
  }