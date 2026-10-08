// Pending invitations, optionally by inviter or email. Expired invitations are excluded until removed.
MATCH (invitation: Invitation)
WHERE invitation.expires_at > datetime()
  AND ($invited_by IS NULL OR EXISTS { (:User {id: $invited_by})-[:INVITED]->(invitation) })
  AND ($email_lower IS NULL OR invitation.email_lower = $email_lower)
WITH invitation ORDER BY invitation.id
RETURN invitation {
  .id, .email, .created_at, .expires_at,
  invited_by: head([(inviter: User)-[:INVITED]->(invitation) | inviter.id]),
  teams: [(invitation)-[offer: OFFERS_TEAM]->(team: Team) | {team_id: team.id, access: offer.access}],
  person_id: head([(invitation)-[:OFFERS_PERSON]->(person: Person) | person.id])
} AS invitation
