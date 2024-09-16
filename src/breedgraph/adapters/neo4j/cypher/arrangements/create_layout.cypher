MERGE (counter: count {name: 'layout'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1

CREATE (layout: Layout {
  id: counter.count,
  name: $name,
  axes: $axes
})

WITH
  layout
// Link to type
CALL {
  WITH layout
  MATCH (type:LayoutType {id: $type})
  CREATE (layout)-[:OF_LAYOUT_TYPE]->(type)
  RETURN type.id as type
}
// Link to location
CALL {
  WITH layout
  MATCH (location:Location {id: $location})
  CREATE (layout)-[:AT_LOCATION]->(location)
  RETURN location.id as location
}
RETURN
  layout {
    .*,
    type: type,
    location: location
  }
