import logging

import pytest

from breedgraph.domain.commands.people import CreatePerson


class RecordingHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


@pytest.mark.asyncio(loop_scope="session")
async def test_message_bus_does_not_log_person_data(bus, isolated_state):
    handler = RecordingHandler()
    logger = logging.getLogger('breedgraph.service_layer.messagebus')
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with pytest.raises(Exception):
            # fails for lack of a legal entity, after the command is logged
            await bus.handle(CreatePerson(
                agent_id=-1, write_team=-1, name='Secret Person Name', informed_attestation=True
            ))
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    assert any('CreatePerson(agent_id=-1, write_team=-1)' in message for message in handler.messages)
    assert not any('Secret Person Name' in message for message in handler.messages)
