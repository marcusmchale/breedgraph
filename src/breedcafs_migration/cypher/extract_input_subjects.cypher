// The subjects each input has records for: the sample unit for samples, otherwise the item label.
// Samples without a unit are left out.
MATCH (r:Record)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item),
      (ii)-[:FOR_INPUT*]->(input:Input)
WITH input, item, count(r) AS item_records
WITH input, item_records,
     CASE WHEN item:Sample THEN item.unit ELSE [l IN labels(item) WHERE l <> 'Item'][0] END AS subject
WHERE subject IS NOT NULL
RETURN input.name AS input, subject, sum(item_records) AS record_count
ORDER BY input, subject
