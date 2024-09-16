MATCH
  (captured: Layout {id: $layout_id})
OPTIONAL MATCH (captured)-[:INCLUDES_LAYOUT*]-(extended:Layout)

WITH captured, coalesce(collect(extended), []) AS layouts
WITH captured + layouts AS arrangement
UNWIND arrangement AS layout
RETURN layout {
  .*,
  type: [(layout)-[:OF_LAYOUT_TYPE]->(type:LayoutType) | type.id][0],
  location: [(layout)-[:AT_LOCATION]->(location:Location) | location.id][0],
  parent_position: [(parent:Layout)-[position:INCLUDES_LAYOUT]->(layout) | [parent.id, position.position]][0]
}
