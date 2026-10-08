MATCH (transfer: ControlTransfer)
WHERE ($recipient_teams IS NULL OR transfer.recipient_team IN $recipient_teams)
  AND ($from_teams IS NULL OR any(team_id IN transfer.from_teams WHERE team_id IN $from_teams))
  AND ($statuses IS NULL OR transfer.status IN $statuses)
RETURN transfer {.*} AS transfer
ORDER BY transfer.id
