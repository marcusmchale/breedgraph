// Teams are marked as deleted rather than removed, so the history of their controls is kept.
// Relabelling as DeletedTeam excludes the team from every query that matches Team.
MATCH (team: Team {id: $team})
OPTIONAL MATCH (parent: Team)-[includes: INCLUDES_TEAM]->(team)
DELETE includes
WITH team, parent.id AS parent_id
CALL (team) {
  MATCH (:User)-[affiliation: READ|WRITE|CURATE|ADMIN]->(team)
  DELETE affiliation
}
CALL (team) {
  MATCH (user: User {default_write_team: team.id})
  SET user.default_write_team = null
}
REMOVE team:Team
SET
  team:DeletedTeam,
  team.parent = parent_id,
  team.deleted_at = datetime.transaction(),
  team.deleted_by = $user_id
