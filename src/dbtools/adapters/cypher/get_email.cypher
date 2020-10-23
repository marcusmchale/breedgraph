MATCH
  (e: Emails)
UNWIND e.allowed as email
WITH email WHERE email = $email
RETURN DISTINCT email