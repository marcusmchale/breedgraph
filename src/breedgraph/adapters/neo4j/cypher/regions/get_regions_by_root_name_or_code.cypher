MATCH (root:Location) WHERE NOT (root)<-[:INCLUDES_LOCATION]-(:Location)
AND (
  root.name =~ $name_regex
  OR
  root.code =~ $code_regex
)
WITH root,
  CASE
    WHEN $name_regex IS NOT NULL AND root.name =~ $name_regex
    THEN [{label: "Location", model_id: root.id, key: "name"}]
    ELSE []
  END
  +
  CASE
    WHEN $code_regex IS NOT NULL AND root.code =~ $code_regex
    THEN [{label: "Location", model_id: root.id, key: "code"}]
    ELSE []
  END AS matches
OPTIONAL MATCH (root)-[:INCLUDES_LOCATION*]->(child:Location)
WITH root, matches, coalesce(collect(child), []) AS children
WITH root.id AS root_id, matches, root + children AS locations
UNWIND locations AS location
OPTIONAL CALL (location) {
  MATCH (location)<-[coord_of:COORDINATE_OF]-(coordinate:Coordinate)
  WITH coordinate, coord_of
  ORDER BY coord_of.position
  RETURN collect(coordinate {.*}) AS coordinates
}
OPTIONAL MATCH (location)-[:OF_LOCATION_TYPE]->(type:LocationType)
OPTIONAL MATCH (parent:Location)-[:INCLUDES_LOCATION]->(location)
WITH root_id, matches, collect(
  location {
    .*,
    coordinates: coalesce(coordinates, []),
    type: type.id,
    parent_id: parent.id
  }
) AS locations
RETURN locations AS region, matches
