MATCH
  (:User {
    name_lower: $admin_name_lower
  })
    -[:SUBMITTED]->(:Submissions)
    -[:SUBMITTED]->(e:Emails)
SET e.allowed = [x IN e.allowed WHERE x <> $email]