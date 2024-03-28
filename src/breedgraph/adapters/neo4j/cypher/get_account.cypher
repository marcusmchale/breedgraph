MATCH
  (user:User {id: ($user_id)})
OPTIONAL MATCH
  (user)-[: READS_FROM]->(reads_from:Team)
OPTIONAL MATCH
  (reads_from)-[:CONTRIBUTES_TO]->(reads_from_parent:Team)
OPTIONAL MATCH
  (user)-[: WRITES_FOR]->(writes_for:Team)
OPTIONAL MATCH
  (writes_for)-[:CONTRIBUTES_TO]->(writes_for_parent:Team)
OPTIONAL MATCH
  (user)-[: ADMINS_FOR]->(admins_for:Team)
OPTIONAL MATCH
  (admins_for)-[:CONTRIBUTES_TO]->(admins_for_parent:Team)
OPTIONAL MATCH
  (user)-[: ALLOWED_REGISTRATION]->(email:Email)
WITH
  user,
  collect({team: reads_from, parent:reads_from_parent}) AS reads_from,
  collect({team: writes_for, parent:writes_for_parent}) AS writes_for,
  collect({team: admins_for, parent:admins_for_parent}) AS admins_for,
  collect(email) AS allowed_emails
RETURN
  user,
  reads_from,
  writes_for,
  admins_for,
  allowed_emails
