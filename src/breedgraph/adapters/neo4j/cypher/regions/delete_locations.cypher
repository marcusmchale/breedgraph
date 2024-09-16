MATCH
  (location: Location) WHERE location.id IN $location_ids
OPTIONAL MATCH
  (location)<-[coordinate_of:COORDINATE_OF]-(coordinate:Coordinate)
DETACH DELETE location, coordinate