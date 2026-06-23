from src.breedgraph.domain import events
from src.breedgraph.service_layer.infrastructure import AbstractNotifications

from ..registry import handlers

@handlers.event_handler()
async def ontology_version_created(
        event: events.ontology.OntologyVersionCreated,
        notifications: AbstractNotifications
):
    pass
    # todo send a notification to ontology admins
    #await notifications.send_to_registered(
    #    [event.email],
    #    email_templates.EmailAddedMessage()
    #)
