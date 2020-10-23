MATCH
  (:User {
    name_lower: $admin_name_lower
  })
  -[:SUBMITTED]->(: Submissions)
  -[:SUBMITTED]->(e: Emails)
SET e.allowed = e.allowed + [$email]