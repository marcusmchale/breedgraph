MATCH (user:User {id: $user_id})-[allowed:ALLOWED_REGISTRATION]->(email:Email {address_lower:$email_lower})
OPTIONAL MATCH (registered: User {email_lower: $email_lower})
FOREACH (u IN CASE WHEN registered IS NOT NULL THEN [registered] ELSE [] END |
  CREATE (user)-[:ALLOWED_REGISTRATION {time:allowed.time}]->(u)
)
DETACH DELETE (email)