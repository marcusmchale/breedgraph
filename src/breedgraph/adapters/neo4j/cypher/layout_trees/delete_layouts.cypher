MATCH
  (layout: Layout) WHERE layout.id IN $layout_ids
DETACH DELETE layout