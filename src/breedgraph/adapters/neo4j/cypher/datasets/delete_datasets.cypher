MATCH
  (dataset: DataSet)-[:INCLUDES_RECORD]->(record:Record)
WHERE dataset.id in $dataset_ids
DETACH DELETE dataset, record