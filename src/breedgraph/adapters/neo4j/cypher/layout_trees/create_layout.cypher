MERGE (counter: Counter {name: 'layout'})
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
OPTIONAL CALL (layout) {
  MATCH (type:LayoutType {id: $type})
  CREATE (layout)-[:OF_LAYOUT_TYPE]->(type)
  RETURN type.id as type
}
// Link to location
OPTIONAL CALL (layout) {
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
