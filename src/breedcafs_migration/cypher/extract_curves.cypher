// One row per curve record (Fluorescence ~ Time), without who recorded it.
// x_values and y_values are lists of equal length.
CALL {
    MATCH (user:User)-[:SUBMITTED]->(:Submissions)-[:SUBMITTED]->(:Records)-[:SUBMITTED]->(:UserFieldInput)
          -[submission:SUBMITTED]->(r:Record)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item)
    RETURN id(user) AS submitter_id, submission.time AS submission_time, r, ii, item
    UNION ALL
    MATCH (r:Record)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item)
    WHERE NOT ()-[:SUBMITTED]->(r)
    RETURN null AS submitter_id, null AS submission_time, r, ii, item
}
MATCH (ii)-[:FOR_INPUT*]->(input:Input)-[:OF_TYPE]->(:RecordType {name: 'Curve'})
RETURN
    id(r) AS record_id,
    submission_time,
    submitter_id,
    item.uid AS item_uid,
    input.name AS input,
    r.time AS time,
    r.text_time AS text_time,
    r.replicate AS replicate,
    r.x_values AS x_values,
    r.y_values AS y_values
ORDER BY submission_time, item_uid, time, replicate
