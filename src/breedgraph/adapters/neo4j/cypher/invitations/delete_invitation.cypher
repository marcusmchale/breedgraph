// Invitations are deleted, with their email address, when accepted, cancelled or expired
MATCH (invitation: Invitation {id: $invitation_id})
DETACH DELETE invitation
