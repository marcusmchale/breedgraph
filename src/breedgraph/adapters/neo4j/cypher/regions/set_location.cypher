MATCH
  (writer: User {id:$writer}),
  (location: Location {id:$id})
MERGE (writer)-[:CREATED]->(ul:UserLocations)
CREATE (ul)-[:UPDATED {time:datetime.transaction()}]->(location)
SET
  location.name = $name,
  location.fullname = $fullname,
  location.description = $description,
  location.code = $code,
  location.address = $address
WITH
  location
// Link to parent
CALL {
  WITH location
  MATCH (location)-[within:WITHIN_LOCATION]->(parent: Location)
  WHERE NOT location.id = $parent
  DELETE within
  WITH DISTINCT location
  MATCH (parent:Location {id: $parent})
  MERGE (location)-[within:WITHIN_LOCATION]->(parent)
  ON CREATE SET within.time = datetime.transaction()
  RETURN collect(parent.id)[0] as parent
}
// Link to type
CALL {
  WITH location
  MATCH (location)-[of_type:OF_LOCATION_TYPE]->(type:LocationType)
  WHERE NOT type.id = $type
  DELETE of_type
  WITH DISTINCT location
  MATCH (type:LocationType {id: $type})
  MERGE (location)-[of_type:OF_LOCATION_TYPE]->(type)
  ON CREATE SET of_type.time = datetime.transaction()
  RETURN collect(type.id)[0] as type
}
// Create coordinates
CALL {
  WITH location
  MATCH (location)<-[coordinate_of:COORDINATE_OF]-(coordinate: Coordinate)
  DELETE coordinate_of, coordinate
  WITH DISTINCT location
  UNWIND $coordinates AS c
  CREATE (location)<-[:COORDINATE_OF]-(coordinate:Coordinate {
    sequence:    c.sequence,
    latitude:    c.latitude,
    longitude:   c.longitude,
    altitude:    c.altitude,
    uncertainty: c.uncertainty,
    description: c.description
  })
  RETURN collect(coordinate {.*}) as coordinates
}
RETURN
  location {
    .*,
    coordinates: coordinates,
    parent: parent,
    children: [(location)<-[:WITHIN_LOCATION]-(child:Location)|child.id],
    type: type,
    controller: {
      writes: writes,
      controls: controls
    }
  }
