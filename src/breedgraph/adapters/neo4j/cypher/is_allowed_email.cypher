MATCH
  (email: Email {address_lower: $address_lower})
RETURN True LIMIT 1