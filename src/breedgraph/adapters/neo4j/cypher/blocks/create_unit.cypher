MERGE (counter: count {name: 'unit'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1

CREATE (unit: Unit {
  id: counter.count,
  name: $name,
  synonyms: $synonyms,
  description: $description
})

WITH
  unit
// Link to subject (required for all units)
CALL {
  WITH unit
  MATCH (subject:Subject {id: $subject})
  CREATE (unit)-[:OF_SUBJECT]->(subject)
  RETURN collect(subject.id)[0] AS subject
}
// Link to positions
CALL {
  WITH unit
  UNWIND $positions as position_map
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
  FOREACH(i in CASE WHEN layout IS NOT NULL THEN [1] ELSE [] END |
    MERGE (position)-[:IN_LAYOUT]->(layout)
  )
  RETURN collect(position {.*, location: location.id, layout: layout.id}) AS positions
}
RETURN
  unit {
    .*,
    subject: subject,
    positions: positions
  }
