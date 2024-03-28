MATCH (user:User {id: $user_id})
MERGE (user)-[allows :ALLOWED_REGISTRATION]->(email:Email {address:$address, address_lower:$address_lower})
ON CREATE SET allows.time = datetime.transaction()
