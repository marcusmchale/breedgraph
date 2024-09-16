MATCH (root: Location) WHERE NOT (root)<-[:INCLUDES_LOCATION]-(:Location)
OPTIONAL MATCH (root)-[:INCLUDES_LOCATION*]->(child:Location)

WITH root, coalesce(collect(child), []) AS children
WITH root + children AS locations
RETURN [ location in locations |
  location {
    .*,
    type: [(location)-[:OF_LOCATION_TYPE]->(type:LocationType) | type.id][0],
    coordinates: [(location)<-[:COORDINATE_OF]-(coordinate:Coordinate) | coordinate {.*}],
    parent_id: [(parent:Location)-[:INCLUDES_LOCATION]->(location) | parent.id][0]
  }
] as region
