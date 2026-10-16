CALL db.index.fulltext.queryNodes("referenceDescription", $description) YIELD node, score
WHERE node.type in $types
RETURN node {.*, contributions: [(node)<-[contributed:CONTRIBUTED_TO]-(person:Person) | {person: person.id, roles: coalesce(contributed.roles, [])}]} as reference, score