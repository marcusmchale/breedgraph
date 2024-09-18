MATCH (layout: Layout {id:$id})
SET
  layout.name = $name,
  layout.axes = $axes
WITH
  layout
// Update type
CALL {
  WITH layout
  MATCH (layout)-[of_type:OF_LAYOUT_TYPE]->(type:LayoutType)
    WHERE NOT type.id = $type
  DELETE of_type
}
CALL {
  WITH layout
  MATCH (type:LayoutType {id: $type})
  MERGE (layout)-[of_type:OF_LAYOUT_TYPE]->(type)
  ON CREATE SET of_type.time = datetime.transaction()
}
// Update location
CALL {
  WITH layout
  MATCH (layout)-[at_location:AT_LOCATION]->(location:Location)
    WHERE NOT location.id = $location
  DELETE at_location
}
CALL {
  WITH layout
  MATCH (location:Location {id: $location})
  MERGE (location)-[at_location:AT_LOCATION]->(location)
  ON CREATE SET at_location.time = datetime.transaction()
}
RETURN NULL