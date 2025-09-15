MATCH (scale: Scale {id:$scale_id})
WITH scale UNWIND range(0, length($categories)) as i
MATCH (scale)-[:HAS_RELATIONSHIP]->(rel:HasCategory)-[:RELATES_TO]->(category:Category {id: $categories[i]})
SET rel.rank = $ranks[i]
