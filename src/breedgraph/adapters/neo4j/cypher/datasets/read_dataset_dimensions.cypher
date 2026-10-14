// What a dataset's records span, read without the records themselves: counts, the time range, the record times
// and values at each percentile from 0 to 100, and the record group codes present by grouping. The percentile
// times take every record start and end; the values are in numeric order when every value is a number and in
// text order otherwise. The caller has checked that the dataset is readable.
MATCH (dataset:Dataset {id: $dataset_id})
CALL (dataset) {
  MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
  RETURN
    count(record) AS record_count,
    count(DISTINCT unit) AS unit_count,
    min(coalesce(record.start, record.end)) AS start,
    max(coalesce(record.end, record.start)) AS end,
    count(record.value) AS value_count,
    count(toFloatOrNull(record.value)) AS number_count
}
CALL (dataset) {
  MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record)
  UNWIND [record.start, record.end] AS time
  WITH time WHERE time IS NOT NULL
  WITH time ORDER BY time
  WITH collect(time) AS times
  RETURN CASE WHEN size(times) = 0 THEN []
    ELSE [p IN range(0, 100) | times[toInteger(round(p * (size(times) - 1) / 100.0))]]
    END AS time_percentiles
}
WITH dataset, record_count, unit_count, start, end, time_percentiles,
  value_count > 0 AND value_count = number_count AS numeric
CALL (dataset, numeric) {
  MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record)
  WITH record.value AS value, numeric WHERE value IS NOT NULL
  WITH value ORDER BY CASE WHEN numeric THEN toFloat(value) END, value
  WITH collect(value) AS values
  RETURN CASE WHEN size(values) = 0 THEN []
    ELSE [p IN range(0, 100) | values[toInteger(round(p * (size(values) - 1) / 100.0))]]
    END AS value_percentiles
}
CALL (dataset) {
  MATCH (dataset)-[:INCLUDES_RECORD]->(:Record)
    -[:IN_GROUP]->(group:RecordGroup)<-[:HAS_GROUP]-(grouping:RecordGrouping)
  WITH DISTINCT grouping.id AS grouping_id, group.code AS code
  ORDER BY grouping_id, code
  WITH grouping_id, collect(code) AS codes
  RETURN collect({grouping_id: grouping_id, codes: codes}) AS groups
}
RETURN {
  record_count: record_count,
  unit_count: unit_count,
  start: start,
  end: end,
  time_percentiles: time_percentiles,
  value_percentiles: value_percentiles,
  groups: groups
} AS dimensions
