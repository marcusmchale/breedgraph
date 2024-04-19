MATCH (user:User {id: $user_id})
MERGE (user)-[allows :ALLOWED_REGISTRATION]->(email:Email {address:$email, address_lower:$email_lower})
ON CREATE SET allows.time = datetime.transaction()
