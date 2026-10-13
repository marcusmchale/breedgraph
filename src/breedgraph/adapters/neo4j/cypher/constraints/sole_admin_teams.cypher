// Teams the user administers where no other user is an authorised admin,
// directly or through a heritable admin affiliation to an ancestor team
MATCH (user: User {id: $user_id})-[:ADMIN {authorisation: 'AUTHORISED'}]->(team: Team)
WHERE NOT EXISTS {
  MATCH (other: User)-[:ADMIN {authorisation: 'AUTHORISED'}]->(team)
  WHERE other.id <> $user_id
}
AND NOT EXISTS {
  MATCH (other: User)-[:ADMIN {authorisation: 'AUTHORISED', heritable: true}]->(:Team)-[:INCLUDES_TEAM*]->(team)
  WHERE other.id <> $user_id
  AND NOT (other)-[:ADMIN {authorisation: 'REVOKED'}]->(team)
}
RETURN collect(team.id) AS team_ids
