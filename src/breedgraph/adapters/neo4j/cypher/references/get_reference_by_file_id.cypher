MATCH (reference: Reference {file_id: $file_id})
RETURN reference {.*}