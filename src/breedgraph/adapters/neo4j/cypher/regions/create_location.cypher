MATCH (writer: User {id:$writer})

MERGE (counter: count {name: 'location'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1

MERGE (writer)-[:CREATED]->(ul:UserLocations)
CREATE (ul)-[created:CREATED {time:datetime.transaction()}]->(location: Location {
  id: counter.count,
  name: $name,
  fullname: $fullname,
  description: $description,
  code: $code,
  address: $address
})

WITH
  location,
  [{user:writer.id, time:created.time}] AS writes
// Establish controls
CALL {
WITH location
UNWIND $controller['controls'] AS control
MATCH (control_team:Team)
  WHERE control_team.id = control['team']
MERGE (control_team)-[:CONTROLS]->(tl:TeamLocations)
CREATE (tl)-[controls:CONTROLS {release: control['release'], time: datetime.transaction()}]->(location)
RETURN
  collect({
    team:    control_team.id,
    release: controls.release,
    time:    controls.time
  }) as controls
}
// Link to parent
CALL {
  WITH location
  MATCH (parent:Location {id: $parent})
  CREATE (location)-[:WITHIN_LOCATION]->(parent)
  RETURN collect(parent.id)[0] as parent
}
// Link to type
CALL {
  WITH location
  MATCH (type:LocationType {id: $type})
  CREATE (location)-[:OF_LOCATION_TYPE]->(type)
  RETURN type.id as type
}
// Create coordinates
CALL {
  WITH location
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
    children: [],
    type: type,
    controller: {
      writes: writes,
      controls: controls
    }
  }
