from breedgraph.domain import events
from breedgraph.service_layer.infrastructure import AbstractErasureLog, ErasureLogEntry

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)


@handlers.event_handler()
async def log_person_erasure(
        event: events.people.PersonErased,
        erasure_log: AbstractErasureLog
):
    """Erasures are logged after they are committed, so a logged erasure always happened."""
    try:
        await erasure_log.append(ErasureLogEntry(person_id=event.person_id, erased_at=event.erased_at))
    except Exception:
        logger.critical(
            f"Failed to log the erasure of Person {event.person_id}. "
            f"Add it to the erasure log, or it will not be applied again after restoring a backup.",
            exc_info=True
        )
        raise
