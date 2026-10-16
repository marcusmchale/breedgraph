MATCH (unit: Unit {id:$id})
SET
  unit.name = $name,
  unit.description = $description
WITH
  unit
// Update subject
CALL (unit) {
  MATCH (unit)-[of_subject:OF_SUBJECT]->(subject:Subject)
    WHERE NOT subject.id = $subject
  DELETE of_subject
}
CALL (unit) {
  MATCH (subject:Subject {id: $subject})
  MERGE (unit)-[of_subject:OF_SUBJECT]->(subject)
  ON CREATE SET of_subject.time = datetime.transaction()
}

// Update germplasm
OPTIONAL CALL (unit) {
  MATCH (unit)-[of_germplasm:OF_GERMPLASM]->(germplasm:Germplasm)
    WHERE NOT germplasm.id = $germplasm
  DELETE of_germplasm
}
OPTIONAL CALL (unit) {
  MATCH (germplasm:Germplasm {id: $germplasm})
  MERGE (unit)-[of_germplasm:OF_GERMPLASM]->(germplasm)
  ON CREATE SET of_germplasm.time = datetime.transaction()
}

// Update positions
OPTIONAL CALL (unit ){
  MATCH (unit)-[:IN_POSITION]->(position:Position)
  DETACH DELETE position
}
CALL (unit) {
  UNWIND $positions AS position_map
  MATCH (location:Location {id: position_map['location_id']})
  OPTIONAL MATCH (layout: Layout {id: position_map['layout_id']})
  CREATE (unit)-[:IN_POSITION]->(position:Position {
    coordinates: position_map['coordinates'],
    start: datetime(position_map['start']),
    start_unit: coalesce(position_map['start_unit'], NULL),
    start_step: coalesce(position_map['start_step'], NULL),
    end:   datetime(position_map['end']),
    end_unit:   coalesce(position_map['end_unit'], NULL),
    end_step:   coalesce(position_map['end_step'], NULL)
  })-[:AT_LOCATION]->(location)
  FOREACH(i IN CASE WHEN layout IS NOT NULL THEN [1] ELSE [] END |
    MERGE (position)-[:IN_LAYOUT]->(layout)
  )
}
RETURN NULL
