// One row per live record, without who recorded it (see submissions.csv and attribution_persons.csv).
// Left out: the structural properties and inputs extracted elsewhere (1.2, 1.4, 1.5), and curve records (extract_curves.cypher).
// The submission is the submission time and the submitter's BreedCAFS node id; both are null for records loaded without one.
CALL {
    MATCH (user:User)-[:SUBMITTED]->(:Submissions)-[:SUBMITTED]->(:Records)-[:SUBMITTED]->(:UserFieldInput)
          -[submission:SUBMITTED]->(r:Record)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item)
    RETURN id(user) AS submitter_id, submission.time AS submission_time, r, ii, item
    UNION ALL
    MATCH (r:Record)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item)
    WHERE NOT ()-[:SUBMITTED]->(r)
    RETURN null AS submitter_id, null AS submission_time, r, ii, item
}
MATCH (ii)-[:FOR_INPUT*]->(input:Input)-[:OF_TYPE]->(type:RecordType)
WHERE type.name <> 'Curve' AND NOT input.name IN [
    'Assign sample to block(s) by name', 'Assign sample to sample(s) by ID', 'Assign sample to tree(s) by ID',
    'Assign tree to block by name', 'Assign variety name', 'Set column', 'Set custom name', 'Set location',
    'Set row', 'Set sample unit', 'Stratum', 'Location (text)'
]
RETURN
    id(r) AS record_id,
    submission_time,
    submitter_id,
    item.uid AS item_uid,
    type.name AS record_type,
    input.name AS input,
    r.value AS value,
    r.time AS time,
    r.text_time AS text_time,
    r.start AS start,
    r.text_start_time AS text_start_time,
    r.end AS end,
    r.text_end_time AS text_end_time,
    r.replicate AS replicate
ORDER BY submission_time, input, item_uid
