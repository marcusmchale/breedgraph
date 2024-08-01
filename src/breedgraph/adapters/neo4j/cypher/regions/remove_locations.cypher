MATCH
  (location: Location) WHERE location.id IN $locations
OPTIONAL MATCH
  (location)<-[writes:CREATED|UPDATED]-(:UserLocations),
  (location)<-[controls:CONTROLS]-(:TeamLocations),
  (location)-[of_type:OF_LOCATION_TYPE]->(:LocationType),
  (location)-[within:WITHIN_LOCATION]->(:Location),
  (location)<-[coordinate_of:COORDINATE_OF]-(coordinate:Coordinate)
DELETE location, writes, controls, of_type, within, coordinate, coordinate_of