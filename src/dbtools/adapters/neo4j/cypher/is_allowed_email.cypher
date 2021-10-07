MATCH
  (user: User)
UNWIND user.allowed_emails AS email
WITH email WHERE email = $email
RETURN True LIMIT 1