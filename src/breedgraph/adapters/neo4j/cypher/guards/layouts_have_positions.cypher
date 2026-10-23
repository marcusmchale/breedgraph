RETURN EXISTS {
  MATCH (:Position)-[:IN_LAYOUT]->(layout: Layout) WHERE layout.id IN $layout_ids
} as in_use
