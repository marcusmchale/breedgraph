MATCH (unit: Unit {id:$id})
SET
  unit.name = $name,
  unit.synonyms = $synonyms,
  unit.description = $description
WITH
  unit
// Update subject
CALL {
  WITH unit
  MATCH (unit)-[of_subject:OF_SUBJECT]->(subject:Subject)
    WHERE NOT subject.id = $subject
  DELETE of_subject
}
CALL {
  WITH unit
  MATCH (subject:Subject {id: $subject})
  MERGE (unit)-[of_subject:OF_SUBJECT]->(subject)
  ON CREATE SET of_subject.time = datetime.transaction()
}
// update germplasm
CALL {
  WITH unit
  MATCH (unit)-[of_germplasm:OF_GERMPLASM]->(germplasm:Germplasm)
    WHERE NOT germplasm.id = $germplasm
  DELETE of_germplasm
}
CALL {
  WITH unit
  MATCH (germplasm: Germplasm {id: $germplasm})
  MERGE (unit)-[of_germplasm:OF_GERMPLASM]->(germplasm)
  ON CREATE SET of_germplasm.time = datetime.transaction()
}
// Update positions
CALL {
  WITH unit
  MATCH (unit)-[:IN_POSITION]->(position:Position)
  DETACH DELETE position
}
CALL {
  WITH unit
  UNWIND $positions AS position_map
  MATCH (location:Location {id: position_map['location']})
  OPTIONAL MATCH (layout: Layout {id: position_map['layout']})
  CREATE (unit)-[:IN_POSITION]->(position:Position {
    coordinates: position_map['coordinates'],
    start: datetime(position_map['start']['str']),
    start_unit: position_map['start']['unit'],
    start_step: position_map['start']['step'],
    end:   datetime(position_map['end']['str']),
    end_unit:   position_map['end']['unit'],
    end_step:   position_map['end']['step']
  })-[:AT_LOCATION]->(location)
  FOREACH(i IN CASE WHEN layout IS NOT NULL THEN [1] ELSE [] END |
    MERGE (position)-[:IN_LAYOUT]->(layout)
  )
}
RETURN NULL
