CALL db.index.fulltext.queryNodes("referenceDescription", $description) YIELD node, score
WHERE node.type in $types
RETURN node {.*} as reference, score