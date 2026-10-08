MERGE (counter: Counter {name: 'control_transfer'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (transfer: ControlTransfer {
  id:              counter.count,
  status:          'PENDING',
  entity_labels:   $entity_labels,
  entity_ids:      $entity_ids,
  from_teams:      $from_teams,
  recipient_team:  $recipient_team,
  keep_from_teams: $keep_from_teams,
  to_teams:        [],
  offered_by:      $offered_by,
  offered_at:      datetime.transaction()
})
RETURN transfer {.*} AS transfer
