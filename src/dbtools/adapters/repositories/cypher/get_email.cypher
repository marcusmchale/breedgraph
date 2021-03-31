MATCH
  (e:Emails)
UNWIND e.allowed AS email
WITH email
  WHERE email = $email
RETURN DISTINCT email