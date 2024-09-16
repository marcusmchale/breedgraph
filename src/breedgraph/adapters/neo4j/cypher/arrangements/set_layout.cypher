MATCH (layout: Layout {id:$id})
SET
  layout.name = $name,
  layout.axes = $axes
WITH
  layout
// Link type
CALL {
  WITH layout
  MATCH (layout)-[of_type:OF_LAYOUT_TYPE]->(type:LayoutType)
  WHERE NOT type.id = $type
  DELETE of_type
  WITH DISTINCT layout
  MATCH (type:LayoutType {id: $type})
  MERGE (layout)-[of_type:OF_LAYOUT_TYPE]->(type)
  ON CREATE SET of_type.time = datetime.transaction()
  RETURN collect(type.id)[0] as type
}
// Link location
CALL {
  WITH layout
  MATCH (layout)-[at_location:AT_LOCATION]->(location:Location)
  WHERE NOT location.id = $location
  DELETE at_location
  WITH DISTINCT layout
  MATCH (location:Location {id: $location})
  MERGE (location)-[at_location:AT_LOCATION]->(location)
  ON CREATE SET at_location.time = datetime.transaction()
  RETURN collect(location.id)[0] as location
}

RETURN
  layout {
    .*,
    type: type,
    location: location,
    units: units
  }
