MATCH (invitation: Invitation {id: $invitation_id})
SET invitation.expires_at = $expires_at
