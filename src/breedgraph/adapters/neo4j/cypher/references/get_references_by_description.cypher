CALL db.index.fulltext.queryNodes("referenceDescription", $description) YIELD node, score
RETURN node {.*} as reference, score