MATCH (invitation: Invitation {id: $invitation_id})
RETURN invitation {
  .id, .email, .created_at, .expires_at,
  invited_by: head([(inviter: User)-[:INVITED]->(invitation) | inviter.id]),
  teams: [(invitation)-[offer: OFFERS_TEAM]->(team: Team) | {team_id: team.id, access: offer.access}],
  person_id: head([(invitation)-[:OFFERS_PERSON]->(person: Person) | person.id])
} AS invitation
