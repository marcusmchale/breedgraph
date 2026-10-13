// The stratum recorded for each branch, for its position in the field's Row, Tree and Stratum layout.
MATCH (branch:Item:Sample)<-[:FOR_ITEM]-(ii:ItemInput)-[:FOR_INPUT*]->(:Input {name: 'Stratum'}),
      (ii)<-[:RECORD_FOR]-(record:Record)
RETURN branch.uid AS item_uid, collect(DISTINCT record.value) AS strata
ORDER BY item_uid
