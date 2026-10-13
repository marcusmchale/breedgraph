// Items not migrated, as they have no data and nothing depends on them:
// samples whose sample unit (subject) was never set, and blocks without trees or samples.
CALL {
    MATCH (sample:Item:Sample)
    WHERE sample.unit IS NULL AND NOT (sample)<-[:FROM|IS_IN*]-(:Item)
    RETURN sample.uid AS item_uid, 'Sample without a sample unit' AS reason
    UNION ALL
    MATCH (block:Item:Block)
    WHERE NOT (block)<-[:IS_IN|FROM*]-(:Item)
    RETURN block.uid AS item_uid, 'Block without trees or samples' AS reason
}
RETURN item_uid, reason
ORDER BY reason, item_uid
