MATCH (invitation: Invitation)
WHERE invitation.expires_at <= datetime()
DETACH DELETE invitation
RETURN count(*) AS deleted
