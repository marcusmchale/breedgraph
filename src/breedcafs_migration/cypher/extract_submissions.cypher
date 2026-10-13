// One row per submission, input and attribution value.
// A submission is the set of records a user submitted at one time.
// Records loaded without a submission (the photosynthesis data) have no submission time, submitter or partner.
CALL {
    MATCH (user:User)-[:SUBMITTED]->(:Submissions)-[:SUBMITTED]->(:Records)-[:SUBMITTED]->(:UserFieldInput)
          -[submission:SUBMITTED]->(r:Record)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item)
    RETURN user, submission.time AS submission_time, r, ii, item
    UNION ALL
    MATCH (r:Record)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item)
    WHERE NOT ()-[:SUBMITTED]->(r)
    RETURN null AS user, null AS submission_time, r, ii, item
}
MATCH (ii)-[:FOR_INPUT*]->(input:Input)-[:OF_TYPE]->(type:RecordType)
WITH user, submission_time, input, type, item,
     CASE WHEN trim(coalesce(r.person, '')) <> '' THEN trim(r.person) END AS person,
     count(r) AS item_records
CALL {
    // samples can reach their field by several paths, but each item has at most one field
    WITH item
    OPTIONAL MATCH (item)-[:IS_IN|FROM*0..]->(field:Field)
    RETURN collect(DISTINCT field.uid)[0] AS field_uid
}
OPTIONAL MATCH (user)-[:AFFILIATED {data_shared: true}]->(partner:Partner)
WITH
    submission_time,
    id(user) AS submitter_id,
    user.name AS submitter,
    partner.name AS partner,
    coalesce(person, 'submitter: ' + user.name) AS attribution,
    type.name AS record_type,
    input.name AS input,
    sum(item_records) AS record_count,
    collect(DISTINCT field_uid) AS field_uids
RETURN
    submission_time,
    CASE WHEN submission_time IS NOT NULL THEN toString(datetime({epochMillis: submission_time})) END AS submitted_at,
    submitter_id, submitter, partner, attribution, record_type, input, record_count, field_uids
ORDER BY submission_time, attribution, input
