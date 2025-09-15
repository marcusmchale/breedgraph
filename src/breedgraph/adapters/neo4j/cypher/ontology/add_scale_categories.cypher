MATCH (scale: Scale {id:$scale_id})
MATCH (category: ScaleCategory)
WHERE category.id in $categories
MERGE (scale)
  -[:HAS_RELATIONSHIP]->(rel:HasCategory)
  -[:RELATES_TO]->(category)
