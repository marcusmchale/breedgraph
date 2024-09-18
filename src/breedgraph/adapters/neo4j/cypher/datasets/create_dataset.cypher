MERGE (counter: count {name: 'dataset'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (dataset: DataSet {id: counter.count})
WITH
  dataset
//Link Term
CALL{
  WITH dataset
  MATCH (term: Variable|EventType|Parameter {id: $term})
  CREATE (dataset)-[for_term:FOR_TERM]->(term)
  RETURN
    collect(term.id)[0] AS term
}
//Link contributors
CALL{
  WITH dataset
  MATCH (contributor: Person) WHERE contributor.id IN $contributors
  CREATE (contributor)-[contributed:CONTRIBUTED_TO]->(dataset)
  RETURN
    collect(contributor.id) AS contributors
}
//Link references
CALL{
  WITH dataset
  MATCH (reference: Reference) WHERE reference.id IN $references
  CREATE (reference)-[reference_for: REFERENCE_FOR]->(dataset)
  RETURN
    collect(reference.id) AS references
}
// Create records
CALL {
  WITH dataset
  MERGE (record_counter: count {name: 'record'})
  ON CREATE SET record_counter.count = 0
  WITH dataset, record_counter
  UNWIND $unit_records AS unit_record
    MATCH (unit:Unit {id:unit_record[0]})
    UNWIND unit_record[1] AS record_data
    SET record_counter.count = record_counter.count + 1
        CREATE (dataset)- [:INCLUDES_RECORD] - >(record:Record {
        id: record_counter.count,
        submitted: datetime.transaction(),
        value:record_data['value'],
        start:datetime(record_data['start']['str']),
        start_unit:record_data['start']['unit'],
        start_step:record_data['start']['step'],
        end:datetime(record_data['end']['str']),
        end_unit:record_data['end']['unit'],
        end_step:record_data['end']['step']
      })-[:FOR_UNIT]->(unit)

      WITH unit, record_data, record
      OPTIONAL MATCH (reference:Reference) WHERE reference.id IN record_data['references']
      FOREACH( i IN CASE WHEN reference IS NOT NULL THEN [1] ELSE [] END |
        CREATE (reference)-[:REFERENCE_FOR]->(record)
      )
      WITH unit, record, [reference IN collect(reference) | reference.id] AS references
    WITH unit, collect(record {.*, references:references}) AS records
  RETURN collect([unit.id, records]) AS unit_records
}
RETURN
  dataset {
    .*,
    term: term,
    unit_records: unit_records,
    contributors: contributors,
    references: references
  }