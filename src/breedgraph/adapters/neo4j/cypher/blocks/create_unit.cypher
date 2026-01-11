MERGE (counter: Counter {name: 'unit'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1

CREATE (unit: Unit {
  id: counter.count,
  name: $name,
  description: $description
})

WITH
  unit
// Link to subject (required for all units)
CALL (unit) {
  MATCH (subject:Subject {id: $subject})
  CREATE (unit)-[:OF_SUBJECT]->(subject)
  RETURN collect(subject.id)[0] AS subject
}
//Link to germplasm (optional)
OPTIONAL CALL (unit) {
  MATCH (germplasm: Germplasm {id: $germplasm})
  CREATE (unit)-[:OF_GERMPLASM]->(germplasm)
  RETURN collect(germplasm.id)[0] as germplasm
}
// Link to positions
CALL (unit) {
  UNWIND $positions as position_map
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
  FOREACH(i in CASE WHEN layout IS NOT NULL THEN [1] ELSE [] END |
    MERGE (position)-[:IN_LAYOUT]->(layout)
  )
  RETURN collect(position {.*, location_id: location.id, layout_id: layout.id}) AS positions
}
RETURN
  unit {
    .*,
    subject: subject,
    positions: positions
  }
