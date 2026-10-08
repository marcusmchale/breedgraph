MATCH (transfer: ControlTransfer {id: $transfer_id})
RETURN transfer {.*} AS transfer
