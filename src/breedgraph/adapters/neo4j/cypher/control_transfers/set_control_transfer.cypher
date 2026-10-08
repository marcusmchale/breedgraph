MATCH (transfer: ControlTransfer {id: $id})
SET
  transfer.status = $status,
  transfer.to_teams = $to_teams,
  transfer.release = $release,
  transfer.accepted_by = $accepted_by,
  transfer.accepted_at = CASE
    WHEN $accepted_by IS NOT NULL THEN coalesce(transfer.accepted_at, datetime.transaction())
  END,
  transfer.rejected_by = $rejected_by,
  transfer.rejected_at = CASE
    WHEN $rejected_by IS NOT NULL THEN coalesce(transfer.rejected_at, datetime.transaction())
  END,
  transfer.cancelled_by = $cancelled_by,
  transfer.cancelled_at = CASE
    WHEN $cancelled_by IS NOT NULL THEN coalesce(transfer.cancelled_at, datetime.transaction())
  END
RETURN transfer {.*} AS transfer
