MATCH (user:User {id: $user})
MERGE (user)-[allows :ALLOWED_REGISTRATION]->(email:Email {address:$email, address_lower:$email_lower})
ON CREATE SET allows.time = datetime.transaction()
