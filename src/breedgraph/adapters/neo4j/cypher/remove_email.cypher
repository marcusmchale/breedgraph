MATCH (user:User {id: $user_id})-[allowed:ALLOWED_REGISTRATION]->(email:Email {address_lower:$address_lower})
OPTIONAL MATCH (registered: User {email_lower: $address_lower})
CREATE (user)-[:ALLOWED_REGISTRATION {time:allowed.time}]->(registered)
DETACH DELETE (email)