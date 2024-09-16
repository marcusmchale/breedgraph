MATCH (root: Layout) WHERE NOT (root)<-[:INCLUDES_LAYOUT]-(:Layout)
OPTIONAL MATCH (root)-[:INCLUDES_LAYOUT*]->(child:Layout)

WITH root, coalesce(collect(child), []) AS children
WITH root + children AS layouts
RETURN [ layout in layouts |
  layout {
    .*,
    type: [(layout)-[:OF_LAYOUT_TYPE]->(type:LayoutType) | type.id][0],
    location: [(layout)-[:AT_LOCATION]->(location:Location) | location.id][0],
    parent_position: [(parent:Layout)-[position:INCLUDES_LAYOUT]->(layout) | [parent.id, position.position]][0]
  }
] as arrangement
